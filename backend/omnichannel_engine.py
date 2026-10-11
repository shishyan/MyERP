"""OpenNow Omnichannel Engine
==========================
Enterprise Omnichannel Telecom & Email Systems Engine reverse-engineered from
Zoho Desk, Zoho ServiceDesk Plus, and GLPI architectures.

Features:
1. Email Integration (Mail-to-Ticket & Conversation Threading):
   - Inbound Email Parser (RFC 822 MIME & JSON webhook formats, multipart MIME, text/HTML body extraction).
   - Smart Conversation Threading: Matches Subject [INC######], In-Reply-To headers, References headers.
     Appends email reply directly to incident journal history as customer replies, or auto-provisions
     new Incidents with Caller auto-provisioning.
   - Outbound Mailer & Notification Templates (Incident Created, Technician Assigned, Incident Resolved, SLA Warning)
     with standard RFC 2822 Message-ID, In-Reply-To, and References headers for robust threading.
   - Inbound Simulator & Mailbox Config management.
2. Phone / Telephony / Computer Telephony Integration (CTI):
   - CTI Screen Pop: Phone number lookup with Caller profile, organization, VIP flag, and active open tickets.
   - Call Logger: cti_calls table tracking direction, technician, duration, disposition, recording URL, call notes.
   - Call-to-Incident conversion workflow.
   - Twilio/PBX Webhook simulation endpoint.
3. High-Performance SQLite storage with WAL mode.
4. Comprehensive standalone test suite in `__main__`.
"""

from __future__ import annotations

import contextlib
import datetime
import email
import email.policy
import email.utils
import json
import logging
import os
import re
import sqlite3
import sys
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from backend.database import DEFAULT_DB_PATH, db

logger = logging.getLogger("opennow.omnichannel")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

omnichannel_router = APIRouter(prefix="/api/v2/omnichannel", tags=["Omnichannel Integration"])


# ============================================================================
# 1. ENUMS & CONSTANTS
# ============================================================================

class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallDisposition(str, Enum):
    RESOLVED_ON_CALL = "resolved_on_call"
    TICKET_CREATED = "ticket_created"
    ESCALATED = "escalated"
    MISSED = "missed"
    VOICEMAIL = "voicemail"


class NotificationTemplateType(str, Enum):
    INCIDENT_CREATED = "incident_created"
    TECHNICIAN_ASSIGNED = "technician_assigned"
    INCIDENT_RESOLVED = "incident_resolved"
    SLA_WARNING = "sla_warning"


INCIDENT_TOKEN_REGEX = re.compile(r'\[?(INC[-_]?\d+)\]?', re.IGNORECASE)


# ============================================================================
# 2. PYDANTIC SCHEMAS
# ============================================================================

class EmailSimulateRequest(BaseModel):
    from_email: str = Field(..., description="Sender email address, e.g. sarah.connor@cyberdyne.io")
    from_name: Optional[str] = Field(None, description="Sender display name")
    to_email: Optional[str] = Field("support@opennow.io", description="Recipient mailbox address")
    subject: str = Field(..., description="Email subject line")
    body_text: str = Field(..., description="Plain-text body of the email")
    body_html: Optional[str] = Field(None, description="HTML formatted body")
    message_id: Optional[str] = Field(None, description="RFC 2822 Message-ID header")
    in_reply_to: Optional[str] = Field(None, description="Message-ID being replied to")
    references: Optional[str] = Field(None, description="Thread reference Message-IDs")
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    raw_mime: Optional[str] = Field(None, description="Optional raw RFC 822 MIME email payload")


class OutboundEmailRequest(BaseModel):
    incident_id: int
    template_type: NotificationTemplateType
    recipient: Optional[str] = None
    custom_subject: Optional[str] = None
    custom_notes: Optional[str] = None


class CallLogCreate(BaseModel):
    call_sid: Optional[str] = Field(None, description="Twilio/PBX Call SID, generated if empty")
    direction: CallDirection = Field(default=CallDirection.INBOUND)
    phone_number: str = Field(..., description="Caller/Recipient phone number, e.g. +15550199")
    caller_id: Optional[int] = Field(None, description="ID from callers table")
    technician_id: Optional[str] = Field("agent.tier1@opennow.io", description="Technician handling the call")
    duration_seconds: int = Field(default=0, ge=0)
    disposition: CallDisposition = Field(default=CallDisposition.TICKET_CREATED)
    recording_url: Optional[str] = Field("", description="URL to call recording audio file")
    call_notes: Optional[str] = Field("", description="Technician call wrap-up notes")
    incident_id: Optional[int] = Field(None, description="Linked incident ID if already created")


class CallConvertIncidentRequest(BaseModel):
    call_sid: Optional[str] = None
    call_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = "IT Services"
    subcategory: Optional[str] = "Telephony & Voice"
    item: Optional[str] = "Phone Support Call"
    priority: Optional[str] = None
    impact: Optional[str] = "2 - Medium"
    urgency: Optional[str] = "2 - Medium"


class CallerCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = ""
    organization: Optional[str] = "General"
    department: Optional[str] = "IT"
    job_title: Optional[str] = ""
    is_vip: Optional[bool] = False


# ============================================================================
# 3. OMNICHANNEL ENGINE CORE
# ============================================================================

class OmnichannelEngine:
    """Core omnichannel telephony, email parser, smart conversation threader,
    and CTI screen-pop manager with WAL-mode SQLite persistence.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_db_dir()
        self.init_schema()
        self.seed_defaults()

    def _ensure_db_dir(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    @contextlib.contextmanager
    def get_connection(self):
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Create tables for email messages, CTI call logs, mailbox configurations, and callers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Callers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS callers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    organization TEXT DEFAULT 'General',
                    department TEXT DEFAULT 'IT',
                    job_title TEXT DEFAULT '',
                    is_vip INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Email messages table (Inbound and Outbound conversation threading)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER,
                    incident_number TEXT,
                    message_id TEXT UNIQUE NOT NULL,
                    in_reply_to TEXT,
                    references_header TEXT,
                    sender TEXT NOT NULL,
                    sender_name TEXT DEFAULT '',
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    body_html TEXT DEFAULT '',
                    direction TEXT NOT NULL DEFAULT 'inbound',
                    has_attachments INTEGER DEFAULT 0,
                    attachments_json TEXT DEFAULT '[]',
                    raw_headers_json TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'processed',
                    created_at TEXT NOT NULL
                );
            """)

            # 3. CTI Phone Calls table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cti_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_sid TEXT UNIQUE NOT NULL,
                    direction TEXT NOT NULL DEFAULT 'inbound',
                    phone_number TEXT NOT NULL,
                    caller_id INTEGER,
                    technician_id TEXT DEFAULT '',
                    duration_seconds INTEGER DEFAULT 0,
                    disposition TEXT DEFAULT 'ticket_created',
                    recording_url TEXT DEFAULT '',
                    call_notes TEXT DEFAULT '',
                    incident_id INTEGER,
                    created_at TEXT NOT NULL
                );
            """)

            # 4. Mailbox configurations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mailbox_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mailbox_name TEXT NOT NULL,
                    email_address TEXT UNIQUE NOT NULL,
                    display_name TEXT DEFAULT '',
                    protocol TEXT DEFAULT 'IMAP',
                    server_host TEXT DEFAULT 'imap.opennow.io',
                    server_port INTEGER DEFAULT 993,
                    use_ssl INTEGER DEFAULT 1,
                    username TEXT DEFAULT '',
                    password_encrypted TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    sync_interval_minutes INTEGER DEFAULT 5,
                    last_sync_at TEXT,
                    last_sync_status TEXT DEFAULT 'idle',
                    sync_error_message TEXT DEFAULT '',
                    total_emails_synced INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # Ensure indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_msg_id ON email_messages(message_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_in_reply_to ON email_messages(in_reply_to);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_inc_id ON email_messages(incident_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_inc_num ON email_messages(incident_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cti_call_sid ON cti_calls(call_sid);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cti_phone ON cti_calls(phone_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cti_incident ON cti_calls(incident_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_caller_phone ON callers(phone);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_caller_email ON callers(email);")

    def seed_defaults(self) -> None:
        """Seed default enterprise callers and mailboxes for instant readiness."""
        now_iso = datetime.datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Seed default mailboxes
            cursor.execute("SELECT COUNT(*) as cnt FROM mailbox_configs")
            if cursor.fetchone()["cnt"] == 0:
                mailboxes = [
                    (
                        "Primary IT Support Desk",
                        "support@opennow.io",
                        "OpenNow Helpdesk",
                        "IMAP",
                        "imap.opennow.io",
                        993,
                        1,
                        "support@opennow.io",
                        1,
                        5,
                        now_iso,
                        "healthy",
                        0,
                        now_iso,
                        now_iso,
                    ),
                    (
                        "Executive & VIP Escalations",
                        "vip-desk@opennow.io",
                        "OpenNow VIP Support",
                        "Exchange",
                        "outlook.office365.com",
                        993,
                        1,
                        "vip-desk@opennow.io",
                        1,
                        2,
                        now_iso,
                        "healthy",
                        0,
                        now_iso,
                        now_iso,
                    ),
                ]
                cursor.executemany("""
                    INSERT INTO mailbox_configs (
                        mailbox_name, email_address, display_name, protocol, server_host,
                        server_port, use_ssl, username, is_active, sync_interval_minutes,
                        last_sync_at, last_sync_status, total_emails_synced, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, mailboxes)

            # Seed default callers
            cursor.execute("SELECT COUNT(*) as cnt FROM callers")
            if cursor.fetchone()["cnt"] == 0:
                callers = [
                    (
                        "Sarah Connor",
                        "sarah.connor@cyberdyne.io",
                        "+15550199",
                        "Cyberdyne Systems",
                        "Executive Office",
                        "Chief Executive Officer",
                        1,
                        now_iso,
                        now_iso,
                    ),
                    (
                        "Alex Mercer",
                        "alex.mercer@gentek.com",
                        "+15550142",
                        "Gentek Corp",
                        "Engineering",
                        "Senior Infrastructure Architect",
                        0,
                        now_iso,
                        now_iso,
                    ),
                    (
                        "Elena Rostova",
                        "elena.r@opennow.io",
                        "+15550188",
                        "OpenNow Enterprise",
                        "Cybersecurity SOC",
                        "Lead SOC Analyst",
                        1,
                        now_iso,
                        now_iso,
                    ),
                ]
                cursor.executemany("""
                    INSERT INTO callers (
                        name, email, phone, organization, department, job_title, is_vip, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, callers)

    # ------------------------------------------------------------------------
    # CALLER MANAGEMENT & RESOLUTION
    # ------------------------------------------------------------------------

    def get_or_create_caller_from_email(self, email_address: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        """Resolves an existing caller by email or automatically provisions a new one."""
        clean_email = email_address.strip().lower()
        now_iso = datetime.datetime.utcnow().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM callers WHERE LOWER(email) = ?", (clean_email,))
            row = cursor.fetchone()
            if row:
                caller_dict = dict(row)
                caller_dict["is_vip"] = bool(caller_dict["is_vip"])
                return caller_dict

            # Check if user exists in the core users table
            cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (clean_email,))
            user_row = cursor.fetchone()
            if user_row:
                name = user_row["full_name"] or user_row["user_name"]
                dept = user_row["department"] or "IT"
                org = "OpenNow Enterprise"
            else:
                if display_name and display_name.strip():
                    name = display_name.strip()
                else:
                    localpart = clean_email.split("@")[0]
                    name = localpart.replace(".", " ").replace("_", " ").replace("-", " ").title()

                domain = clean_email.split("@")[-1] if "@" in clean_email else "general.com"
                org_part = domain.split(".")[0]
                org = f"{org_part.capitalize()} Corp" if org_part not in ("gmail", "yahoo", "hotmail", "outlook") else "General Client"
                dept = "General"

            # Auto-detect VIP status
            vip_keywords = ["vip", "ceo", "cto", "cio", "cfo", "director", "executive", "vp", "president", "chief"]
            is_vip = 1 if any(k in clean_email or k in name.lower() for k in vip_keywords) else 0

            cursor.execute("""
                INSERT INTO callers (
                    name, email, phone, organization, department, job_title, is_vip, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, clean_email, "", org, dept, "Employee", is_vip, now_iso, now_iso))
            caller_id = cursor.lastrowid

            cursor.execute("SELECT * FROM callers WHERE id = ?", (caller_id,))
            new_row = dict(cursor.fetchone())
            new_row["is_vip"] = bool(new_row["is_vip"])
            return new_row

    def get_caller_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Finds caller by phone number (exact or digit normalized)."""
        raw_phone = phone.strip()
        digits = re.sub(r"\D", "", raw_phone)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Exact match on raw phone
            cursor.execute("SELECT * FROM callers WHERE phone = ?", (raw_phone,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res["is_vip"] = bool(res["is_vip"])
                return res

            # 2. Normalized match or contains
            cursor.execute("SELECT * FROM callers WHERE phone IS NOT NULL AND phone != ''")
            for c in cursor.fetchall():
                c_digits = re.sub(r"\D", "", c["phone"])
                if c_digits and (c_digits == digits or digits.endswith(c_digits) or c_digits.endswith(digits)):
                    res = dict(c)
                    res["is_vip"] = bool(res["is_vip"])
                    return res

            return None

    def list_callers(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM callers ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["is_vip"] = bool(d["is_vip"])
                result.append(d)
            return result

    def create_caller(self, caller_data: CallerCreate) -> Dict[str, Any]:
        now_iso = datetime.datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO callers (
                    name, email, phone, organization, department, job_title, is_vip, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                caller_data.name.strip(),
                caller_data.email.strip().lower(),
                caller_data.phone or "",
                caller_data.organization or "General",
                caller_data.department or "IT",
                caller_data.job_title or "",
                1 if caller_data.is_vip else 0,
                now_iso,
                now_iso,
            ))
            new_id = cursor.lastrowid
            cursor.execute("SELECT * FROM callers WHERE id = ?", (new_id,))
            d = dict(cursor.fetchone())
            d["is_vip"] = bool(d["is_vip"])
            return d

    # ------------------------------------------------------------------------
    # INBOUND EMAIL PARSER
    # ------------------------------------------------------------------------

    def parse_raw_mime_email(self, raw_mime: str) -> Dict[str, Any]:
        """Parses standard RFC 822 MIME email string into structured attributes."""
        msg = email.message_from_string(raw_mime, policy=email.policy.default)

        # Parse From
        from_hdr = msg.get("From", "")
        sender_name, sender_email = email.utils.parseaddr(from_hdr)
        if not sender_email and "@" in from_hdr:
            sender_email = from_hdr.strip()

        # Parse To
        to_hdr = msg.get("To", "support@opennow.io")
        _, recipient_email = email.utils.parseaddr(to_hdr)
        if not recipient_email and "@" in to_hdr:
            recipient_email = to_hdr.strip()

        subject = str(msg.get("Subject", "No Subject")).strip()
        message_id = msg.get("Message-ID", "").strip()
        in_reply_to = msg.get("In-Reply-To", "").strip()
        references = msg.get("References", "").strip()

        body_text_parts: List[str] = []
        body_html_parts: List[str] = []
        attachments: List[Dict[str, Any]] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get_content_disposition() or "")

                if disposition == "attachment":
                    attachments.append({
                        "filename": part.get_filename() or "attachment.dat",
                        "content_type": content_type,
                        "size": len(part.get_payload(decode=True) or b""),
                    })
                elif content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body_text_parts.append(payload.decode(charset, errors="replace"))
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body_html_parts.append(payload.decode(charset, errors="replace"))
        else:
            payload = msg.get_payload(decode=True)
            content_type = msg.get_content_type()
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace") if payload else ""
            if content_type == "text/html":
                body_html_parts.append(decoded)
            else:
                body_text_parts.append(decoded)

        body_text = "\n".join(body_text_parts).strip()
        body_html = "\n".join(body_html_parts).strip()

        if not body_text and body_html:
            # Strip tags for fallback text
            body_text = re.sub(r"<[^>]+>", " ", body_html).strip()

        return {
            "from_email": sender_email or "unknown@sender.com",
            "from_name": sender_name or "",
            "to_email": recipient_email or "support@opennow.io",
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "message_id": message_id or self.generate_message_id(),
            "in_reply_to": in_reply_to,
            "references": references,
            "attachments": attachments,
        }

    def generate_message_id(self, incident_number: Optional[str] = None) -> str:
        """Generates standard RFC 2822 compliant Message-ID."""
        ts = int(datetime.datetime.utcnow().timestamp())
        rand_tok = uuid.uuid4().hex[:8]
        if incident_number:
            return f"<{incident_number}.{ts}.{rand_tok}@opennow.io>"
        return f"<mail.{ts}.{rand_tok}@opennow.io>"

    # ------------------------------------------------------------------------
    # SMART CONVERSATION THREADING & INCIDENT RESOLUTION
    # ------------------------------------------------------------------------

    def find_matching_incident(
        self,
        subject: str,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Matches an inbound email to an existing incident using:
        1. Subject incident code ([INC######] / INC######).
        2. In-Reply-To Message-ID matching.
        3. References header Message-ID matching.
        """
        # 1. Subject incident token match
        token_match = INCIDENT_TOKEN_REGEX.search(subject)
        if token_match:
            raw_token = token_match.group(1).upper()
            # Normalize to INC0000001 or find directly
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM v2_incidents WHERE UPPER(incident_number) = ? OR UPPER(incident_number) LIKE ?",
                    (raw_token, f"%{raw_token}%")
                )
                row = cursor.fetchone()
                if row:
                    return dict(row), "subject_token"

                # Check if it was formatted like INC-123 -> digits
                digits = re.sub(r"\D", "", raw_token)
                if digits:
                    int_id = int(digits)
                    cursor.execute("SELECT * FROM v2_incidents WHERE id = ? OR incident_number LIKE ?", (int_id, f"INC%{int_id:04d}%"))
                    row = cursor.fetchone()
                    if row:
                        return dict(row), "subject_token_digits"

        # 2. In-Reply-To Message-ID header matching
        if in_reply_to and in_reply_to.strip():
            clean_in_reply = in_reply_to.strip()
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT incident_id, incident_number FROM email_messages WHERE message_id = ? AND incident_id IS NOT NULL",
                    (clean_in_reply,)
                )
                row = cursor.fetchone()
                if row and row["incident_id"]:
                    cursor.execute("SELECT * FROM v2_incidents WHERE id = ?", (row["incident_id"],))
                    inc_row = cursor.fetchone()
                    if inc_row:
                        return dict(inc_row), "in_reply_to_header"

        # 3. References header matching
        if references and references.strip():
            ref_tokens = re.findall(r"<[^>]+>", references)
            if not ref_tokens:
                ref_tokens = references.strip().split()

            with self.get_connection() as conn:
                cursor = conn.cursor()
                for ref in ref_tokens:
                    clean_ref = ref.strip()
                    cursor.execute(
                        "SELECT incident_id FROM email_messages WHERE message_id = ? AND incident_id IS NOT NULL",
                        (clean_ref,)
                    )
                    row = cursor.fetchone()
                    if row and row["incident_id"]:
                        cursor.execute("SELECT * FROM v2_incidents WHERE id = ?", (row["incident_id"],))
                        inc_row = cursor.fetchone()
                        if inc_row:
                            return dict(inc_row), "references_header"

        return None, "none"

    def process_inbound_email(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Main inbound mail-to-ticket processing pipeline:
        - If matching incident found: appends reply to incident history journal.
        - If no match found: auto-provisions Caller, auto-creates Incident, sends auto-confirmation.
        """
        now_iso = datetime.datetime.utcnow().isoformat()

        # Check if raw RFC 822 was provided
        if payload.get("raw_mime"):
            parsed = self.parse_raw_mime_email(payload["raw_mime"])
        else:
            parsed = {
                "from_email": (payload.get("from_email") or payload.get("sender") or "user@client.com").strip(),
                "from_name": (payload.get("from_name") or payload.get("sender_name") or "").strip(),
                "to_email": (payload.get("to_email") or payload.get("recipient") or "support@opennow.io").strip(),
                "subject": (payload.get("subject") or "No Subject").strip(),
                "body_text": (payload.get("body_text") or "").strip(),
                "body_html": (payload.get("body_html") or "").strip(),
                "message_id": (payload.get("message_id") or self.generate_message_id()).strip(),
                "in_reply_to": (payload.get("in_reply_to") or "").strip(),
                "references": (payload.get("references") or "").strip(),
                "attachments": payload.get("attachments") or [],
            }

        sender_email = parsed["from_email"].strip().lower()
        sender_name = parsed["from_name"].strip()
        subject = parsed["subject"]
        body_text = parsed["body_text"]
        body_html = parsed["body_html"]
        message_id = parsed["message_id"]
        in_reply_to = parsed["in_reply_to"]
        references = parsed["references"]
        attachments = parsed["attachments"]

        # 1. Resolve or provision Caller
        caller = self.get_or_create_caller_from_email(sender_email, sender_name)
        is_vip = caller.get("is_vip", False)

        # 2. Check for conversation threading match
        matched_incident, match_reason = self.find_matching_incident(
            subject=subject,
            in_reply_to=in_reply_to,
            references=references,
        )

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if matched_incident:
                # -----------------------------------------------------------
                # CASE A: THREADED CUSTOMER REPLY
                # -----------------------------------------------------------
                inc_id = matched_incident["id"]
                inc_num = matched_incident["incident_number"]
                current_state = matched_incident["state"]

                # If ticket was waiting for customer ("Pending Customer" or "On Hold"), auto-resume to "In Progress"
                new_state = current_state
                if current_state in ("On Hold", "Pending Customer", "Pending_Customer", "Awaiting Customer"):
                    new_state = "In Progress"

                # Append directly to Incident History / Journal
                journal_note = f"[Email Inbound Reply]\nFrom: {sender_name or sender_email} <{sender_email}>\n\n{body_text}"
                cursor.execute("""
                    INSERT INTO v2_incident_history (
                        incident_id, actor, action, from_state, to_state, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (inc_id, sender_name or sender_email, "CUSTOMER_REPLY", current_state, new_state, journal_note, now_iso))
                journal_id = cursor.lastrowid

                # Update incident state and updated_at
                cursor.execute("""
                    UPDATE v2_incidents
                    SET state = ?, updated_at = ?
                    WHERE id = ?
                """, (new_state, now_iso, inc_id))

                # Store email message record
                cursor.execute("""
                    INSERT INTO email_messages (
                        incident_id, incident_number, message_id, in_reply_to, references_header,
                        sender, sender_name, recipient, subject, body_text, body_html,
                        direction, has_attachments, attachments_json, raw_headers_json, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    inc_id,
                    inc_num,
                    message_id,
                    in_reply_to,
                    references,
                    sender_email,
                    sender_name,
                    parsed["to_email"],
                    subject,
                    body_text,
                    body_html,
                    "inbound",
                    1 if attachments else 0,
                    json.dumps(attachments),
                    json.dumps({"match_reason": match_reason}),
                    "threaded_reply",
                    now_iso,
                ))
                email_record_id = cursor.lastrowid

                # Update mailbox sync counter
                cursor.execute("""
                    UPDATE mailbox_configs
                    SET total_emails_synced = total_emails_synced + 1, last_sync_at = ?
                    WHERE LOWER(email_address) = LOWER(?)
                """, (now_iso, parsed["to_email"]))

                return {
                    "action": "threaded_reply",
                    "matched_by": match_reason,
                    "incident_id": inc_id,
                    "incident_number": inc_num,
                    "incident_title": matched_incident["title"],
                    "state": new_state,
                    "caller": caller,
                    "journal_entry_id": journal_id,
                    "email_message_id": email_record_id,
                    "message_id": message_id,
                    "message": f"Successfully threaded inbound reply into journal of {inc_num}.",
                }

            else:
                # -----------------------------------------------------------
                # CASE B: NEW INCIDENT CREATION
                # -----------------------------------------------------------
                cursor.execute("SELECT id FROM v2_incidents ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                next_id = (row["id"] + 1) if row else 1
                new_incident_number = f"INC{next_id:07d}"

                priority = "P2" if is_vip else "P3"
                impact = "1 - High" if is_vip else "2 - Medium"
                urgency = "1 - High" if is_vip else "2 - Medium"
                sla_hours = 2.0 if is_vip else 4.0
                sla_due_dt = datetime.datetime.utcnow() + datetime.timedelta(hours=sla_hours)
                sla_due_at = sla_due_dt.isoformat()

                title = subject if subject and subject != "No Subject" else f"Inbound Request from {caller['name']}"

                cursor.execute("""
                    INSERT INTO v2_incidents (
                        incident_number, title, description, category, subcategory, item,
                        impact, urgency, priority, state, caller, assigned_to, assignment_group,
                        ci_id, resolution_code, resolution_notes, root_cause, pause_reason,
                        created_at, updated_at, resolved_at, closed_at, sla_target_hours,
                        sla_due_at, sla_breached, sla_paused_total_seconds, sla_paused_at,
                        is_fcr, custom_fields
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_incident_number,
                    title,
                    body_text,
                    "IT Services",
                    "Email Inbound",
                    "Service Request",
                    impact,
                    urgency,
                    priority,
                    "New",
                    sender_email,
                    "",
                    "Service Desk Tier 1" if not is_vip else "Executive Escalation Team",
                    "",
                    "",
                    "",
                    "",
                    "",
                    now_iso,
                    now_iso,
                    None,
                    None,
                    sla_hours,
                    sla_due_at,
                    0,
                    0.0,
                    None,
                    0,
                    json.dumps({"origin": "email", "caller_id": caller["id"], "is_vip": is_vip}),
                ))
                new_inc_id = cursor.lastrowid

                # Initial audit journal entry
                cursor.execute("""
                    INSERT INTO v2_incident_history (
                        incident_id, actor, action, from_state, to_state, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_inc_id,
                    caller["name"] or sender_email,
                    "CREATE_VIA_EMAIL",
                    "",
                    "New",
                    f"Auto-provisioned incident from inbound email Message-ID: {message_id}",
                    now_iso,
                ))

                # Store email record
                cursor.execute("""
                    INSERT INTO email_messages (
                        incident_id, incident_number, message_id, in_reply_to, references_header,
                        sender, sender_name, recipient, subject, body_text, body_html,
                        direction, has_attachments, attachments_json, raw_headers_json, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_inc_id,
                    new_incident_number,
                    message_id,
                    in_reply_to,
                    references,
                    sender_email,
                    sender_name,
                    parsed["to_email"],
                    subject,
                    body_text,
                    body_html,
                    "inbound",
                    1 if attachments else 0,
                    json.dumps(attachments),
                    json.dumps({"caller_id": caller["id"], "is_vip": is_vip}),
                    "created_incident",
                    now_iso,
                ))
                email_record_id = cursor.lastrowid

                # Update mailbox sync counter
                cursor.execute("""
                    UPDATE mailbox_configs
                    SET total_emails_synced = total_emails_synced + 1, last_sync_at = ?
                    WHERE LOWER(email_address) = LOWER(?)
                """, (now_iso, parsed["to_email"]))

        # Send outbound auto-reply confirmation email (Incident Created template)
        outbound_reply = self.send_notification(
            incident_id=new_inc_id,
            template_type=NotificationTemplateType.INCIDENT_CREATED,
            recipient=sender_email,
            parent_message_id=message_id,
        )

        return {
            "action": "created_incident",
            "matched_by": "none",
            "incident_id": new_inc_id,
            "incident_number": new_incident_number,
            "incident_title": title,
            "priority": priority,
            "state": "New",
            "caller": caller,
            "email_message_id": email_record_id,
            "message_id": message_id,
            "auto_reply": outbound_reply,
            "message": f"Successfully created ticket {new_incident_number} for {sender_email}.",
        }

    # ------------------------------------------------------------------------
    # OUTBOUND MAILER & NOTIFICATION TEMPLATES
    # ------------------------------------------------------------------------

    def render_notification_template(
        self,
        template_type: NotificationTemplateType,
        incident: Dict[str, Any],
        caller: Dict[str, Any],
        custom_notes: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Renders Subject, Text Body, and HTML Body for given notification template."""
        inc_num = incident.get("incident_number", "INC0000000")
        title = incident.get("title", "")
        priority = incident.get("priority", "P3")
        state = incident.get("state", "New")
        assigned_to = incident.get("assigned_to") or "Service Desk Tier 1"
        caller_name = caller.get("name") or incident.get("caller") or "Valued Customer"
        sla_hours = incident.get("sla_target_hours", 4.0)
        sla_due_at = incident.get("sla_due_at", "N/A")
        res_notes = incident.get("resolution_notes") or "Ticket successfully resolved by engineer."
        root_cause = incident.get("root_cause") or "Standard operation procedure completed."

        if template_type == NotificationTemplateType.INCIDENT_CREATED:
            subject = f"[{inc_num}] Incident Created: {title}"
            body_text = f"""Dear {caller_name},

Thank you for reaching out to OpenNow IT Support. Your request has been logged.

Ticket Details:
- Incident Number: {inc_num}
- Summary: {title}
- Priority: {priority}
- Status: {state}
- Target SLA: {sla_hours} hours (Due: {sla_due_at})

Our support engineering team has been notified. You can reply directly to this email to attach logs, screenshots, or additional information.

Best regards,
OpenNow Enterprise IT Service Desk
"""
            body_html = f"""<div style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
  <h2 style="color: #2563eb;">Incident Created: [{inc_num}]</h2>
  <p>Dear <strong>{caller_name}</strong>,</p>
  <p>Your support request has been registered in OpenNow.</p>
  <table style="border-collapse: collapse; width: 100%; max-width: 600px; margin: 20px 0;">
    <tr style="background: #f1f5f9;"><td style="padding: 8px; border: 1px solid #cbd5e1;"><strong>Ticket Number</strong></td><td style="padding: 8px; border: 1px solid #cbd5e1;">{inc_num}</td></tr>
    <tr><td style="padding: 8px; border: 1px solid #cbd5e1;"><strong>Summary</strong></td><td style="padding: 8px; border: 1px solid #cbd5e1;">{title}</td></tr>
    <tr style="background: #f1f5f9;"><td style="padding: 8px; border: 1px solid #cbd5e1;"><strong>Priority</strong></td><td style="padding: 8px; border: 1px solid #cbd5e1;">{priority}</td></tr>
    <tr><td style="padding: 8px; border: 1px solid #cbd5e1;"><strong>Target SLA</strong></td><td style="padding: 8px; border: 1px solid #cbd5e1;">{sla_hours} hours</td></tr>
  </table>
  <p>You can <strong>reply directly to this email</strong> to provide additional information.</p>
  <p style="color: #64748b; font-size: 12px; margin-top: 30px;">OpenNow Autonomous ITIL Service Desk</p>
</div>"""

        elif template_type == NotificationTemplateType.TECHNICIAN_ASSIGNED:
            subject = f"[{inc_num}] Technician Assigned: {assigned_to}"
            body_text = f"""Dear {caller_name},

Technician {assigned_to} has been assigned to your ticket {inc_num} ({title}).
Work is now actively underway.

Notes: {custom_notes or 'Investigation started.'}

Best regards,
OpenNow IT Support Team
"""
            body_html = f"""<div style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
  <h2 style="color: #0284c7;">Technician Assigned: [{inc_num}]</h2>
  <p>Dear <strong>{caller_name}</strong>,</p>
  <p>Technician <strong>{assigned_to}</strong> has been assigned to your incident.</p>
  <p><em>{custom_notes or 'Investigation in progress.'}</em></p>
</div>"""

        elif template_type == NotificationTemplateType.INCIDENT_RESOLVED:
            subject = f"[{inc_num}] Incident Resolved: {title}"
            body_text = f"""Dear {caller_name},

Your incident {inc_num} has been marked as Resolved.

Resolution Details:
- Solution: {res_notes}
- Root Cause: {root_cause}

If your issue persists, simply reply to this email to automatically reopen the ticket.

Best regards,
OpenNow Enterprise IT Service Desk
"""
            body_html = f"""<div style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
  <h2 style="color: #16a34a;">Incident Resolved: [{inc_num}]</h2>
  <p>Dear <strong>{caller_name}</strong>,</p>
  <p>Your ticket <strong>{inc_num}</strong> has been marked as resolved.</p>
  <div style="background: #f0fdf4; border-left: 4px solid #16a34a; padding: 12px; margin: 15px 0;">
    <strong>Resolution Notes:</strong><br>{res_notes}<br><br>
    <strong>Root Cause:</strong><br>{root_cause}
  </div>
  <p>If you need further help, reply to this email to automatically reopen the incident.</p>
</div>"""

        elif template_type == NotificationTemplateType.SLA_WARNING:
            subject = f"[{inc_num}] URGENT SLA Warning: Resolution SLA at Risk"
            body_text = f"""URGENT SLA WARNING:

Incident: {inc_num} ({title})
Priority: {priority}
Assigned To: {assigned_to}
SLA Target: {sla_hours} hours
Due At: {sla_due_at}

Immediate technician intervention required to prevent SLA breach.
"""
            body_html = f"""<div style="font-family: Arial, sans-serif; color: #991b1b; line-height: 1.6;">
  <h2 style="color: #dc2626;">SLA Breach Warning: [{inc_num}]</h2>
  <p>Incident <strong>{inc_num}</strong> ({title}) is approaching its SLA threshold.</p>
  <p>Target Due: <strong>{sla_due_at}</strong> | Assigned: <strong>{assigned_to}</strong></p>
</div>"""

        else:
            subject = f"[{inc_num}] Notification: {title}"
            body_text = f"Update regarding {inc_num}: {custom_notes or title}"
            body_html = f"<p>Update regarding {inc_num}: {custom_notes or title}</p>"

        return subject, body_text, body_html

    def send_notification(
        self,
        incident_id: int,
        template_type: NotificationTemplateType,
        recipient: Optional[str] = None,
        parent_message_id: Optional[str] = None,
        custom_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates standard RFC 2822 Message-ID, builds outbound email, and stores it in WAL DB."""
        now_iso = datetime.datetime.utcnow().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM v2_incidents WHERE id = ?", (incident_id,))
            inc_row = cursor.fetchone()
            if not inc_row:
                raise ValueError(f"Incident ID {incident_id} not found.")
            incident = dict(inc_row)

            # Determine recipient and caller
            target_recipient = recipient or incident.get("caller") or "user@client.com"
            caller = self.get_or_create_caller_from_email(target_recipient)

            subject, body_text, body_html = self.render_notification_template(
                template_type=template_type,
                incident=incident,
                caller=caller,
                custom_notes=custom_notes,
            )

            inc_num = incident.get("incident_number", "INC0000000")
            outbound_msg_id = self.generate_message_id(inc_num)

            # Find latest inbound message ID if parent_message_id not specified
            in_reply_to = parent_message_id or ""
            references = parent_message_id or ""
            if not in_reply_to:
                cursor.execute(
                    "SELECT message_id FROM email_messages WHERE incident_id = ? AND direction = 'inbound' ORDER BY id DESC LIMIT 1",
                    (incident_id,)
                )
                prev_in = cursor.fetchone()
                if prev_in:
                    in_reply_to = prev_in["message_id"]
                    references = prev_in["message_id"]

            cursor.execute("""
                INSERT INTO email_messages (
                    incident_id, incident_number, message_id, in_reply_to, references_header,
                    sender, sender_name, recipient, subject, body_text, body_html,
                    direction, has_attachments, attachments_json, raw_headers_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident_id,
                inc_num,
                outbound_msg_id,
                in_reply_to,
                references,
                "support@opennow.io",
                "OpenNow IT Service Desk",
                target_recipient,
                subject,
                body_text,
                body_html,
                "outbound",
                0,
                "[]",
                json.dumps({"template_type": template_type.value}),
                "sent",
                now_iso,
            ))
            email_id = cursor.lastrowid

            # Add entry to incident history
            cursor.execute("""
                INSERT INTO v2_incident_history (
                    incident_id, actor, action, notes, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                incident_id,
                "MailerBot",
                "NOTIFICATION_SENT",
                f"Sent {template_type.value} notification to {target_recipient} ({outbound_msg_id})",
                now_iso,
            ))

        return {
            "id": email_id,
            "incident_id": incident_id,
            "incident_number": inc_num,
            "recipient": target_recipient,
            "subject": subject,
            "message_id": outbound_msg_id,
            "in_reply_to": in_reply_to,
            "references": references,
            "template_type": template_type.value,
            "status": "sent",
            "created_at": now_iso,
        }

    # ------------------------------------------------------------------------
    # CTI SCREEN POP & PHONE TELEPHONY INTEGRATION
    # ------------------------------------------------------------------------

    def phone_lookup(self, phone: str) -> Dict[str, Any]:
        """CTI Screen Pop: Lookup incoming phone number.
        Returns Caller identity, organization, VIP status, and active open tickets.
        """
        clean_phone = phone.strip()
        caller = self.get_caller_by_phone(clean_phone)

        if not caller:
            return {
                "found": False,
                "phone": clean_phone,
                "caller": None,
                "organization": "Unknown Organization",
                "is_vip": False,
                "open_tickets": [],
                "active_ticket_count": 0,
                "recent_calls": [],
            }

        # Query active open tickets for this caller
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, incident_number, title, priority, state, created_at, sla_due_at, assigned_to
                FROM v2_incidents
                WHERE (caller = ? OR caller = ?)
                  AND state NOT IN ('Resolved', 'Closed', 'Cancelled')
                ORDER BY id DESC
            """, (caller["email"], caller["name"]))
            tickets = [dict(r) for r in cursor.fetchall()]

            # Query recent calls for this caller / phone
            cursor.execute("""
                SELECT id, call_sid, direction, duration_seconds, disposition, technician_id, incident_id, created_at
                FROM cti_calls
                WHERE phone_number = ? OR caller_id = ?
                ORDER BY id DESC LIMIT 5
            """, (clean_phone, caller["id"]))
            recent_calls = [dict(r) for r in cursor.fetchall()]

        return {
            "found": True,
            "phone": clean_phone,
            "caller": caller,
            "organization": caller.get("organization") or "General",
            "is_vip": caller.get("is_vip", False),
            "open_tickets": tickets,
            "active_ticket_count": len(tickets),
            "recent_calls": recent_calls,
        }

    def log_call(self, call_data: CallLogCreate) -> Dict[str, Any]:
        """Logs a phone call entry in cti_calls table."""
        now_iso = datetime.datetime.utcnow().isoformat()
        call_sid = call_data.call_sid or f"CA{uuid.uuid4().hex}"

        # Resolve caller_id if not explicitly provided
        caller_id = call_data.caller_id
        if not caller_id and call_data.phone_number:
            caller = self.get_caller_by_phone(call_data.phone_number)
            if caller:
                caller_id = caller["id"]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cti_calls (
                    call_sid, direction, phone_number, caller_id, technician_id,
                    duration_seconds, disposition, recording_url, call_notes,
                    incident_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                call_sid,
                call_data.direction.value,
                call_data.phone_number.strip(),
                caller_id,
                call_data.technician_id or "",
                call_data.duration_seconds,
                call_data.disposition.value,
                call_data.recording_url or "",
                call_data.call_notes or "",
                call_data.incident_id,
                now_iso,
            ))
            call_id = cursor.lastrowid
            cursor.execute("SELECT * FROM cti_calls WHERE id = ?", (call_id,))
            return dict(cursor.fetchone())

    def convert_call_to_incident(self, req: CallConvertIncidentRequest) -> Dict[str, Any]:
        """Converts an existing call log directly into a newly provisioned incident,
        binding call notes, recording URL, and caller metadata.
        """
        now_iso = datetime.datetime.utcnow().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if req.call_sid:
                cursor.execute("SELECT * FROM cti_calls WHERE call_sid = ?", (req.call_sid,))
            elif req.call_id:
                cursor.execute("SELECT * FROM cti_calls WHERE id = ?", (req.call_id,))
            else:
                raise ValueError("Either call_sid or call_id must be provided.")

            call_row = cursor.fetchone()
            if not call_row:
                raise ValueError("Call record not found.")

            call = dict(call_row)

            # Resolve caller info
            caller = None
            if call.get("caller_id"):
                cursor.execute("SELECT * FROM callers WHERE id = ?", (call["caller_id"],))
                c_row = cursor.fetchone()
                if c_row:
                    caller = dict(c_row)

            if not caller and call.get("phone_number"):
                caller = self.get_caller_by_phone(call["phone_number"])

            caller_name = caller["name"] if caller else f"Caller ({call['phone_number']})"
            caller_email = caller["email"] if caller else f"phone_{call['phone_number']}@opennow.io"
            is_vip = caller.get("is_vip", False) if caller else False

            # Generate Incident Number
            cursor.execute("SELECT id FROM v2_incidents ORDER BY id DESC LIMIT 1")
            last_inc = cursor.fetchone()
            next_id = (last_inc["id"] + 1) if last_inc else 1
            inc_number = f"INC{next_id:07d}"

            priority = req.priority or ("P2" if is_vip else "P3")
            impact = req.impact or ("1 - High" if is_vip else "2 - Medium")
            urgency = req.urgency or ("1 - High" if is_vip else "2 - Medium")
            sla_hours = 2.0 if is_vip else 4.0
            sla_due_dt = datetime.datetime.utcnow() + datetime.timedelta(hours=sla_hours)

            title = req.title or f"Phone Support: Call with {caller_name}"
            desc = req.description or (
                f"Call Notes: {call.get('call_notes') or 'N/A'}\n\n"
                f"Call SID: {call['call_sid']}\n"
                f"Direction: {call['direction']}\n"
                f"Duration: {call['duration_seconds']} seconds\n"
                f"Recording URL: {call.get('recording_url') or 'N/A'}"
            )

            cursor.execute("""
                INSERT INTO v2_incidents (
                    incident_number, title, description, category, subcategory, item,
                    impact, urgency, priority, state, caller, assigned_to, assignment_group,
                    ci_id, resolution_code, resolution_notes, root_cause, pause_reason,
                    created_at, updated_at, resolved_at, closed_at, sla_target_hours,
                    sla_due_at, sla_breached, sla_paused_total_seconds, sla_paused_at,
                    is_fcr, custom_fields
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inc_number,
                title,
                desc,
                req.category or "IT Services",
                req.subcategory or "Telephony & Voice",
                req.item or "Phone Support Call",
                impact,
                urgency,
                priority,
                "New",
                caller_email,
                call.get("technician_id") or "",
                "Service Desk Tier 1",
                "",
                "",
                "",
                "",
                "",
                now_iso,
                now_iso,
                None,
                None,
                sla_hours,
                sla_due_dt.isoformat(),
                0,
                0.0,
                None,
                0,
                json.dumps({"call_sid": call["call_sid"], "phone_number": call["phone_number"], "is_vip": is_vip}),
            ))
            inc_id = cursor.lastrowid

            # Update call record
            cursor.execute("""
                UPDATE cti_calls
                SET incident_id = ?, disposition = 'ticket_created'
                WHERE id = ?
            """, (inc_id, call["id"]))

            # Add to incident history
            cursor.execute("""
                INSERT INTO v2_incident_history (
                    incident_id, actor, action, notes, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                inc_id,
                call.get("technician_id") or "CTI-System",
                "CONVERTED_FROM_CALL",
                f"Created from phone call {call['call_sid']} ({call['duration_seconds']}s)",
                now_iso,
            ))

            cursor.execute("SELECT * FROM v2_incidents WHERE id = ?", (inc_id,))
            created_incident = dict(cursor.fetchone())

            cursor.execute("SELECT * FROM cti_calls WHERE id = ?", (call["id"],))
            updated_call = dict(cursor.fetchone())

        return {
            "success": True,
            "incident": created_incident,
            "call": updated_call,
            "caller": caller,
            "message": f"Successfully converted call {call['call_sid']} to ticket {inc_number}.",
        }

    def list_calls(
        self,
        limit: int = 50,
        offset: int = 0,
        direction: Optional[str] = None,
        disposition: Optional[str] = None,
        phone_number: Optional[str] = None,
        technician_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM cti_calls WHERE 1=1"
        params: List[Any] = []

        if direction:
            query += " AND direction = ?"
            params.append(direction.strip())
        if disposition:
            query += " AND disposition = ?"
            params.append(disposition.strip())
        if phone_number:
            query += " AND phone_number LIKE ?"
            params.append(f"%{phone_number.strip()}%")
        if technician_id:
            query += " AND technician_id LIKE ?"
            params.append(f"%{technician_id.strip()}%")

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    # ------------------------------------------------------------------------
    # MAILBOX INBOX & SYNC STATUS
    # ------------------------------------------------------------------------

    def get_inbox_overview(self) -> Dict[str, Any]:
        """Returns configured mailboxes, sync statuses, email counters, and recent messages."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mailbox_configs ORDER BY id ASC")
            mailboxes = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) as cnt FROM email_messages WHERE direction = 'inbound'")
            inbound_cnt = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM email_messages WHERE direction = 'outbound'")
            outbound_cnt = cursor.fetchone()["cnt"]

            cursor.execute("""
                SELECT id, incident_id, incident_number, sender, recipient, subject, direction, status, created_at
                FROM email_messages
                ORDER BY id DESC LIMIT 15
            """)
            recent_messages = [dict(r) for r in cursor.fetchall()]

        return {
            "mailboxes": mailboxes,
            "summary": {
                "total_mailboxes": len(mailboxes),
                "active_mailboxes": sum(1 for m in mailboxes if m["is_active"]),
                "total_inbound_emails": inbound_cnt,
                "total_outbound_emails": outbound_cnt,
            },
            "recent_messages": recent_messages,
        }


# Singleton engine instance
omnichannel_engine = OmnichannelEngine()


# ============================================================================
# 4. REST API ROUTER ENDPOINTS
# ============================================================================

@omnichannel_router.post("/email/simulate", tags=["Omnichannel Email"])
def email_simulate(payload: EmailSimulateRequest) -> Dict[str, Any]:
    """Simulates inbound email reception for live testing, auto-provisions ticket
    or threads directly to incident journal history.
    """
    try:
        result = omnichannel_engine.process_inbound_email(payload.dict())
        return result
    except Exception as e:
        logger.exception("Error simulating inbound email")
        raise HTTPException(status_code=500, detail=str(e))


@omnichannel_router.get("/email/inbox", tags=["Omnichannel Email"])
def email_inbox() -> Dict[str, Any]:
    """Lists mailbox channels, sync statuses, and recent email conversations."""
    return omnichannel_engine.get_inbox_overview()


@omnichannel_router.get("/email/messages", tags=["Omnichannel Email"])
def list_email_messages(
    incident_id: Optional[int] = Query(None, description="Filter by incident ID"),
    direction: Optional[str] = Query(None, description="'inbound' or 'outbound'"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM email_messages WHERE 1=1"
    params: List[Any] = []
    if incident_id:
        query += " AND incident_id = ?"
        params.append(incident_id)
    if direction:
        query += " AND direction = ?"
        params.append(direction.strip())
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with omnichannel_engine.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


@omnichannel_router.post("/email/send", tags=["Omnichannel Email"])
def send_email_notification(payload: OutboundEmailRequest) -> Dict[str, Any]:
    """Generates and logs an outbound notification email with RFC 2822 Message-ID threading."""
    try:
        res = omnichannel_engine.send_notification(
            incident_id=payload.incident_id,
            template_type=payload.template_type,
            recipient=payload.recipient,
            custom_notes=payload.custom_notes,
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.exception("Error sending notification")
        raise HTTPException(status_code=500, detail=str(e))


@omnichannel_router.get("/phone/lookup", tags=["Omnichannel Telephony"])
def phone_screen_pop_lookup(
    phone: str = Query(..., description="Incoming phone number, e.g. +15550199 or 5550199")
) -> Dict[str, Any]:
    """CTI Screen Pop: Lookup incoming phone number. Returns caller profile,
    organization, VIP status, and open tickets.
    """
    return omnichannel_engine.phone_lookup(phone)


@omnichannel_router.post("/phone/call", status_code=status.HTTP_201_CREATED, tags=["Omnichannel Telephony"])
def log_phone_call(payload: CallLogCreate) -> Dict[str, Any]:
    """Logs a call record into the CTI call logger table."""
    try:
        return omnichannel_engine.log_call(payload)
    except Exception as e:
        logger.exception("Error logging phone call")
        raise HTTPException(status_code=500, detail=str(e))


@omnichannel_router.post("/phone/create-incident", status_code=status.HTTP_201_CREATED, tags=["Omnichannel Telephony"])
def convert_call_to_incident(payload: CallConvertIncidentRequest) -> Dict[str, Any]:
    """Converts a phone call directly into an incident, recording call notes and audio link."""
    try:
        return omnichannel_engine.convert_call_to_incident(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error converting call to incident")
        raise HTTPException(status_code=500, detail=str(e))


@omnichannel_router.post("/phone/webhook", tags=["Omnichannel Telephony"])
async def pbx_twilio_webhook(request: Request) -> Response:
    """Twilio / PBX Telephony Webhook simulation. Accepts JSON or urlencoded form."""
    content_type = request.headers.get("content-type", "")
    data: Dict[str, Any] = {}
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)

    call_sid = data.get("CallSid") or data.get("call_sid") or f"CA{uuid.uuid4().hex}"
    from_phone = data.get("From") or data.get("from") or data.get("phone_number") or "+15550000"
    duration = int(data.get("CallDuration") or data.get("DialCallDuration") or data.get("duration") or 0)
    recording_url = data.get("RecordingUrl") or data.get("recording_url") or ""
    direction = CallDirection.INBOUND if data.get("Direction", "inbound") == "inbound" else CallDirection.OUTBOUND

    call_log = omnichannel_engine.log_call(
        CallLogCreate(
            call_sid=call_sid,
            direction=direction,
            phone_number=from_phone,
            duration_seconds=duration,
            disposition=CallDisposition.TICKET_CREATED,
            recording_url=recording_url,
            call_notes=f"Twilio PBX Webhook: {data.get('CallStatus', 'completed')}",
        )
    )

    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Thank you for calling OpenNow IT Support. Your call SID is {call_sid}.</Say>
</Response>"""
    return Response(content=twiml_response, media_type="application/xml")


@omnichannel_router.get("/phone/calls", tags=["Omnichannel Telephony"])
def list_calls(
    direction: Optional[str] = Query(None, description="'inbound' or 'outbound'"),
    disposition: Optional[str] = Query(None, description="Disposal code"),
    phone_number: Optional[str] = Query(None, description="Phone number filter"),
    technician_id: Optional[str] = Query(None, description="Technician filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[Dict[str, Any]]:
    """Lists CTI call history with filtering and pagination."""
    return omnichannel_engine.list_calls(
        limit=limit,
        offset=offset,
        direction=direction,
        disposition=disposition,
        phone_number=phone_number,
        technician_id=technician_id,
    )


@omnichannel_router.get("/callers", tags=["Omnichannel Telephony"])
def list_callers(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> List[Dict[str, Any]]:
    return omnichannel_engine.list_callers(limit=limit, offset=offset)


@omnichannel_router.post("/callers", status_code=status.HTTP_201_CREATED, tags=["Omnichannel Telephony"])
def create_caller(payload: CallerCreate) -> Dict[str, Any]:
    return omnichannel_engine.create_caller(payload)


# ============================================================================
# 5. COMPREHENSIVE UNIT TEST SUITE
# ============================================================================

if __name__ == "__main__":
    import tempfile
    import unittest

    print("======================================================================")
    print("RUNNING OMNICHANNEL ENGINE COMPREHENSIVE UNIT TEST SUITE")
    print("======================================================================")

    class TestOmnichannelEngine(unittest.TestCase):
        def setUp(self):
            # Create a separate isolated test database
            self.test_dir = tempfile.mkdtemp()
            self.db_path = os.path.join(self.test_dir, "test_omnichannel.db")
            self.engine = OmnichannelEngine(db_path=self.db_path)

            # Ensure v2_incidents & v2_incident_history exist in this test db
            with self.engine.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS v2_incidents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_number TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        category TEXT DEFAULT '',
                        subcategory TEXT DEFAULT '',
                        item TEXT DEFAULT '',
                        impact TEXT DEFAULT '2 - Medium',
                        urgency TEXT DEFAULT '2 - Medium',
                        priority TEXT DEFAULT 'P3',
                        state TEXT DEFAULT 'New',
                        caller TEXT,
                        assigned_to TEXT DEFAULT '',
                        assignment_group TEXT DEFAULT '',
                        ci_id TEXT DEFAULT '',
                        resolution_code TEXT DEFAULT '',
                        resolution_notes TEXT DEFAULT '',
                        root_cause TEXT DEFAULT '',
                        pause_reason TEXT DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        resolved_at TEXT,
                        closed_at TEXT,
                        sla_target_hours REAL DEFAULT 4.0,
                        sla_due_at TEXT,
                        sla_breached INTEGER DEFAULT 0,
                        sla_paused_total_seconds REAL DEFAULT 0.0,
                        sla_paused_at TEXT,
                        is_fcr INTEGER DEFAULT 0,
                        custom_fields TEXT DEFAULT '{}'
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS v2_incident_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_id INTEGER NOT NULL,
                        actor TEXT NOT NULL,
                        action TEXT NOT NULL,
                        from_state TEXT DEFAULT '',
                        to_state TEXT DEFAULT '',
                        notes TEXT DEFAULT '',
                        created_at TEXT NOT NULL
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        external_id TEXT UNIQUE,
                        user_name TEXT UNIQUE NOT NULL,
                        full_name TEXT,
                        email TEXT,
                        role TEXT DEFAULT 'end_user',
                        department TEXT,
                        created_at TEXT NOT NULL
                    );
                """)

        def tearDown(self):
            try:
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
            except Exception:
                pass

        def test_1_email_to_ticket_creation_and_caller_provisioning(self):
            """Verify that an inbound email from a new sender creates a ticket,
            provisions the caller, assigns priority, and generates an auto-reply.
            """
            result = self.engine.process_inbound_email({
                "from_email": "jane.doe@acme.org",
                "from_name": "Jane Doe",
                "to_email": "support@opennow.io",
                "subject": "VPN connection drops every 10 minutes",
                "body_text": "I am experiencing repeated disconnections when connecting to the EU gateway.",
                "message_id": "<test-msg-001@acme.org>",
            })

            self.assertEqual(result["action"], "created_incident")
            self.assertTrue(result["incident_number"].startswith("INC"))
            self.assertEqual(result["state"], "New")
            self.assertIsNotNone(result["auto_reply"])
            self.assertIn("INC", result["auto_reply"]["subject"])

            # Verify caller was auto-provisioned
            caller = self.engine.get_or_create_caller_from_email("jane.doe@acme.org")
            self.assertEqual(caller["name"], "Jane Doe")
            self.assertEqual(caller["organization"], "Acme Corp")
            self.assertFalse(caller["is_vip"])

        def test_2_smart_conversation_threading_via_subject_incident_token(self):
            """Verify that an email with [INC######] in subject appends directly
            to the incident journal history as a customer reply.
            """
            # Create original incident
            init_res = self.engine.process_inbound_email({
                "from_email": "john.connor@resistance.net",
                "from_name": "John Connor",
                "to_email": "support@opennow.io",
                "subject": "Firewall rules blocking telemetry port 9090",
                "body_text": "Outbound port 9090 is blocked.",
                "message_id": "<init-firewall-01@resistance.net>",
            })
            inc_id = init_res["incident_id"]
            inc_num = init_res["incident_number"]

            # Set incident to 'Pending Customer'
            with self.engine.get_connection() as conn:
                conn.execute("UPDATE v2_incidents SET state = 'Pending Customer' WHERE id = ?", (inc_id,))

            # Customer replies with subject containing [INC######]
            reply_res = self.engine.process_inbound_email({
                "from_email": "john.connor@resistance.net",
                "from_name": "John Connor",
                "to_email": "support@opennow.io",
                "subject": f"Re: [{inc_num}] Firewall rules blocking telemetry port 9090",
                "body_text": "Here is the traceroute log: hop 3 times out at 192.168.1.1.",
                "message_id": "<reply-firewall-02@resistance.net>",
                "in_reply_to": "<init-firewall-01@resistance.net>",
            })

            self.assertEqual(reply_res["action"], "threaded_reply")
            self.assertEqual(reply_res["incident_id"], inc_id)
            self.assertEqual(reply_res["incident_number"], inc_num)
            # Ticket should auto-resume to 'In Progress'
            self.assertEqual(reply_res["state"], "In Progress")

            # Check journal history
            with self.engine.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM v2_incident_history WHERE incident_id = ? AND action = 'CUSTOMER_REPLY'", (inc_id,))
                history_row = cursor.fetchone()
                self.assertIsNotNone(history_row)
                self.assertIn("traceroute log", history_row["notes"])

        def test_3_smart_conversation_threading_via_in_reply_to_header(self):
            """Verify that when subject has no [INC] token, In-Reply-To header
            matches previous Message-ID and threads correctly.
            """
            init_res = self.engine.process_inbound_email({
                "from_email": "dev@techcorp.com",
                "from_name": "Dev User",
                "to_email": "support@opennow.io",
                "subject": "Database slow query warning",
                "body_text": "Postgres queries on users table taking 4 seconds.",
                "message_id": "<parent-db-query@techcorp.com>",
            })
            inc_id = init_res["incident_id"]
            inc_num = init_res["incident_number"]

            # Reply without ticket number in subject, but with In-Reply-To set to outbound auto-reply
            auto_reply_msg_id = init_res["auto_reply"]["message_id"]
            reply_res = self.engine.process_inbound_email({
                "from_email": "dev@techcorp.com",
                "from_name": "Dev User",
                "to_email": "support@opennow.io",
                "subject": "Re: Query optimization follow up",
                "body_text": "I added an index on created_at and latency dropped to 10ms.",
                "message_id": "<child-db-query@techcorp.com>",
                "in_reply_to": auto_reply_msg_id,
            })

            self.assertEqual(reply_res["action"], "threaded_reply")
            self.assertEqual(reply_res["incident_id"], inc_id)
            self.assertEqual(reply_res["matched_by"], "in_reply_to_header")

        def test_4_cti_phone_lookup_and_screen_pop(self):
            """Verify CTI Screen Pop returns Caller profile, VIP status, and open tickets."""
            # 1. Lookup seeded VIP Sarah Connor (+15550199)
            pop = self.engine.phone_lookup("+15550199")
            self.assertTrue(pop["found"])
            self.assertEqual(pop["caller"]["name"], "Sarah Connor")
            self.assertTrue(pop["is_vip"])
            self.assertEqual(pop["organization"], "Cyberdyne Systems")

            # 2. Create an open ticket for Sarah
            self.engine.process_inbound_email({
                "from_email": "sarah.connor@cyberdyne.io",
                "from_name": "Sarah Connor",
                "to_email": "support@opennow.io",
                "subject": "T-800 unit firmware update required",
                "body_text": "Firmware binary verification failed on sector 7.",
            })

            # Re-lookup screen pop: should include open ticket
            pop_updated = self.engine.phone_lookup("+15550199")
            self.assertGreaterEqual(pop_updated["active_ticket_count"], 1)
            self.assertIn("firmware", pop_updated["open_tickets"][0]["title"].lower())

            # 3. Lookup unknown phone
            unknown = self.engine.phone_lookup("+19999999999")
            self.assertFalse(unknown["found"])
            self.assertEqual(unknown["active_ticket_count"], 0)

        def test_5_call_logging_and_convert_to_incident(self):
            """Verify logging a phone call and converting it to an incident with notes."""
            call_log = self.engine.log_call(CallLogCreate(
                call_sid="CAtestcall12345",
                direction=CallDirection.INBOUND,
                phone_number="+15550199",
                technician_id="tier2.agent@opennow.io",
                duration_seconds=184,
                disposition=CallDisposition.RESOLVED_ON_CALL,
                recording_url="https://s3.opennow.io/recordings/call_12345.mp3",
                call_notes="VIP customer reported server latency. Diagnosed DNS lookup delay.",
            ))
            self.assertEqual(call_log["call_sid"], "CAtestcall12345")
            self.assertEqual(call_log["duration_seconds"], 184)

            # Convert call to incident
            conv_res = self.engine.convert_call_to_incident(CallConvertIncidentRequest(
                call_sid="CAtestcall12345",
                title="DNS Server Resolution Delay reported via Phone",
                category="Network",
                subcategory="DNS",
            ))

            self.assertTrue(conv_res["success"])
            incident = conv_res["incident"]
            self.assertIn("INC", incident["incident_number"])
            self.assertIn("DNS", incident["title"])
            self.assertEqual(conv_res["call"]["incident_id"], incident["id"])
            self.assertEqual(conv_res["call"]["disposition"], "ticket_created")

        def test_6_outbound_notification_templates(self):
            """Verify outbound mail templates generate proper Message-ID headers and content."""
            # Create an incident
            inc_res = self.engine.process_inbound_email({
                "from_email": "test@domain.com",
                "subject": "Printer jam on floor 3",
                "body_text": "Paper jammed in feeder tray.",
            })
            inc_id = inc_res["incident_id"]

            # Send Technician Assigned notification
            assigned_mail = self.engine.send_notification(
                incident_id=inc_id,
                template_type=NotificationTemplateType.TECHNICIAN_ASSIGNED,
                custom_notes="Dispatched field technician Marcus to replace pickup rollers.",
            )
            self.assertIn("Technician Assigned", assigned_mail["subject"])
            self.assertTrue(assigned_mail["message_id"].startswith("<INC"))

            # Send Incident Resolved notification
            with self.engine.get_connection() as conn:
                conn.execute(
                    "UPDATE v2_incidents SET resolution_notes = 'Replaced worn rubber rollers.', root_cause = 'Hardware wear' WHERE id = ?",
                    (inc_id,)
                )

            resolved_mail = self.engine.send_notification(
                incident_id=inc_id,
                template_type=NotificationTemplateType.INCIDENT_RESOLVED,
            )
            self.assertIn("Incident Resolved", resolved_mail["subject"])

    suite = unittest.TestLoader().loadTestsFromTestCase(TestOmnichannelEngine)
    runner = unittest.TextTestRunner(verbosity=2)
    test_result = runner.run(suite)
    if not test_result.wasSuccessful():
        sys.exit(1)
    print("======================================================================")
    print("ALL OMNICHANNEL ENGINE TESTS PASSED SUCCESSFULLY!")
    print("======================================================================")
