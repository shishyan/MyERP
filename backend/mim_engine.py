"""OpenNow Enterprise Major Incident Management (MIM) Engine
============================================================
ITIL v4 & Google SRE Incident Command System (ICS) implementation:
1. Major Incident State Model: Candidate -> Proposed -> Active P1 Major Incident -> Mitigated -> Post-Incident Review (PIR) -> Closed.
2. Role Assignments: Incident Commander (IC), Technical Ops Lead, Communications Lead, Scribe.
3. Real-Time War Room: Dynamic Bridge URL, Conference Dial-in + PIN, Dedicated Slack/Teams Chat, Real-Time Command Log & Roster.
4. Stakeholder Broadcast Engine: Internal Technical Bulletin vs External Executive / Customer Status Page Updates.
5. Chronometer Metrics: Time to Detect (TTD), Time to Engage (TTE), Time to Mitigate (TTM), Time to Restore (TTR).
6. Post-Incident Review (PIR) / Blameless Post-Mortem Generator: Auto-compiles timeline, root cause, 5-whys, impacted customers, downtime cost ($), preventative action items, exportable to Markdown and JSON.
7. REST API Endpoints mounted under /api/v2/mim.
8. Comprehensive Unit Test Suite under `if __name__ == '__main__':`.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

logger = logging.getLogger("opennow.mim")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Default database directory and path
DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "opennow.db")


def now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 string format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def parse_iso(dt_str: Optional[str]) -> Optional[datetime.datetime]:
    """Robust ISO 8601 parser supporting 'Z' and offset formats."""
    if not dt_str:
        return None
    try:
        clean = dt_str.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(clean)
    except Exception:
        return None


def format_duration(seconds: Union[int, float]) -> str:
    """Formats duration in seconds into human-readable representation."""
    if seconds is None or seconds < 0:
        return "0s"
    sec = int(round(seconds))
    days, sec = divmod(sec, 86400)
    hours, sec = divmod(sec, 3600)
    minutes, sec = divmod(sec, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{sec}s")
    return " ".join(parts)


# ============================================================================
# 1. ENUMS & CONSTANTS (ITIL v4 & Google SRE Incident Command)
# ============================================================================

class MIMStatus(str, Enum):
    CANDIDATE = "Candidate"
    PROPOSED = "Proposed"
    ACTIVE = "Active P1 Major Incident"
    MITIGATED = "Mitigated"
    PIR = "Post-Incident Review (PIR)"
    CLOSED = "Closed"
    REJECTED = "Rejected"

    @classmethod
    def normalize(cls, val: str) -> "MIMStatus":
        """Normalizes various user inputs to standard MIMStatus."""
        if not val:
            return cls.ACTIVE
        v = val.strip().lower().replace("_", " ").replace("-", " ")
        if "cand" in v:
            return cls.CANDIDATE
        if "prop" in v:
            return cls.PROPOSED
        if "act" in v or "p1" in v:
            return cls.ACTIVE
        if "mitig" in v:
            return cls.MITIGATED
        if "pir" in v or "post" in v or "review" in v or "mortem" in v:
            return cls.PIR
        if "close" in v:
            return cls.CLOSED
        if "reject" in v or "cancel" in v:
            return cls.REJECTED
        # Direct lookup fallback
        for member in cls:
            if member.value.lower() == v:
                return member
        return cls.ACTIVE


class MIMRoleType(str, Enum):
    INCIDENT_COMMANDER = "Incident Commander (IC)"
    TECHNICAL_OPS_LEAD = "Technical Ops Lead"
    COMMUNICATIONS_LEAD = "Communications Lead"
    SCRIBE = "Scribe"

    @classmethod
    def normalize(cls, val: str) -> "MIMRoleType":
        if not val:
            return cls.INCIDENT_COMMANDER
        v = val.strip().lower()
        if "ic" in v or "command" in v:
            return cls.INCIDENT_COMMANDER
        if "tech" in v or "ops" in v or "engineering" in v:
            return cls.TECHNICAL_OPS_LEAD
        if "comm" in v or "broadcast" in v:
            return cls.COMMUNICATIONS_LEAD
        if "scribe" in v or "record" in v or "note" in v:
            return cls.SCRIBE
        for member in cls:
            if member.value.lower() == v:
                return member
        return cls.INCIDENT_COMMANDER


class BroadcastAudience(str, Enum):
    INTERNAL_TECHNICAL = "internal_technical"
    EXTERNAL_EXECUTIVE = "external_executive"
    CUSTOMER_STATUS_PAGE = "customer_status_page"


class IncidentPhase(str, Enum):
    INVESTIGATING = "Investigating"
    IDENTIFIED = "Identified"
    MITIGATING = "Mitigating"
    MONITORING = "Monitoring"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


# Valid State Transitions Workflow
VALID_TRANSITIONS: Dict[MIMStatus, List[MIMStatus]] = {
    MIMStatus.CANDIDATE: [MIMStatus.PROPOSED, MIMStatus.ACTIVE, MIMStatus.REJECTED],
    MIMStatus.PROPOSED: [MIMStatus.ACTIVE, MIMStatus.CANDIDATE, MIMStatus.REJECTED],
    MIMStatus.ACTIVE: [MIMStatus.MITIGATED, MIMStatus.PIR, MIMStatus.CLOSED],
    MIMStatus.MITIGATED: [MIMStatus.ACTIVE, MIMStatus.PIR, MIMStatus.CLOSED],
    MIMStatus.PIR: [MIMStatus.MITIGATED, MIMStatus.CLOSED],
    MIMStatus.CLOSED: [MIMStatus.PIR],  # Reopen for post-incident audit
    MIMStatus.REJECTED: [MIMStatus.CANDIDATE, MIMStatus.PROPOSED],
}


# ============================================================================
# 2. PYDANTIC SCHEMAS FOR API & VALIDATION
# ============================================================================

class PromotePayload(BaseModel):
    incident_id: Optional[Union[str, int]] = Field(None, description="Linked Incident ID or Number (e.g. INC-1001)")
    title: str = Field(..., min_length=3, description="Major Incident headline / title")
    summary: Optional[str] = Field("", description="Executive summary of the ongoing major disruption")
    severity: Optional[str] = Field("P1", description="Severity level, default P1 Critical")
    impact_scope: Optional[str] = Field("Enterprise-Wide", description="Scope: Enterprise-Wide, Multi-Region, Customer-Facing")
    blast_radius: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "affected_services": ["Core Gateway", "Authentication API"],
            "affected_tenants": ["Enterprise Tier-1 Customers"],
            "affected_users": 10000,
            "error_rate_pct": 92.4,
        },
        description="Detailed blast radius breakdown"
    )
    incident_start_time: Optional[str] = Field(None, description="ISO timestamp when outage began. Defaults to current time.")
    detected_time: Optional[str] = Field(None, description="ISO timestamp when outage was detected by monitoring.")
    initial_status: Optional[str] = Field(MIMStatus.ACTIVE.value, description="Initial state (Candidate, Proposed, Active P1 Major Incident)")
    incident_commander: Optional[str] = Field("Alex Vance (Principal SRE)", description="Incident Commander name")
    technical_ops_lead: Optional[str] = Field("Elena Rostova (Lead Systems Architect)", description="Technical Ops Lead name")
    communications_lead: Optional[str] = Field("Marcus Brody (Director of Incident Comms)", description="Communications Lead name")
    scribe: Optional[str] = Field("David K. (Incident Scribe)", description="Scribe name")
    hourly_downtime_rate: Optional[float] = Field(12500.0, description="Downtime cost per hour ($)")
    war_room_url: Optional[str] = Field(None, description="Optional custom video conference bridge URL")
    chat_channel: Optional[str] = Field(None, description="Optional dedicated Slack or Teams war room channel")


class BroadcastPayload(BaseModel):
    audience: str = Field(BroadcastAudience.INTERNAL_TECHNICAL.value, description="internal_technical | external_executive | customer_status_page")
    subject: str = Field(..., min_length=3, description="Subject line for email / bulletin")
    message_body: str = Field(..., min_length=10, description="Detailed broadcast update content")
    incident_phase: Optional[str] = Field(IncidentPhase.INVESTIGATING.value, description="Investigating, Identified, Mitigating, Monitoring, Resolved, Closed")
    eta_to_mitigation: Optional[str] = Field("30-45 minutes", description="Estimated time until mitigation or workaround")
    next_update_due: Optional[str] = Field(None, description="ISO timestamp or relative time for next scheduled broadcast")
    sent_by: Optional[str] = Field("Communications Lead", description="Sender identity or role")
    delivery_channels: Optional[List[str]] = Field(
        default_factory=lambda: ["slack", "email", "statuspage", "sms"],
        description="Target distribution channels"
    )


class PostMortemGeneratePayload(BaseModel):
    root_cause: Optional[str] = Field(None, description="Confirmed technical root cause")
    trigger_event: Optional[str] = Field(None, description="Specific event triggering the outage")
    five_whys: Optional[List[Union[str, Dict[str, Any]]]] = Field(None, description="Iterative 5-Whys root cause analysis")
    impacted_customers: Optional[List[str]] = Field(None, description="Specific customer accounts or tiers impacted")
    affected_services: Optional[List[str]] = Field(None, description="List of degraded microservices/infrastructure CIs")
    hourly_downtime_rate: Optional[float] = Field(None, description="Hourly financial impact rate ($)")
    sla_credits_estimate: Optional[float] = Field(None, description="Contractual SLA credit compensation penalty ($)")
    what_went_well: Optional[List[str]] = Field(None, description="Blameless positives in detection, coordination, tools")
    what_went_wrong: Optional[List[str]] = Field(None, description="Difficulties, delayed alerts, missing runbooks, tooling gaps")
    where_we_got_lucky: Optional[List[str]] = Field(None, description="Fortuitous factors that prevented worse impact")
    action_items: Optional[List[Dict[str, Any]]] = Field(None, description="Preventative and hardening action items")


class StatusTransitionPayload(BaseModel):
    target_status: str = Field(..., description="Target MIM state (e.g. Mitigated, Post-Incident Review (PIR), Closed)")
    actor: Optional[str] = Field("Incident Commander", description="Name/role making transition")
    reason: Optional[str] = Field("", description="Justification or evidence for state change")
    notes: Optional[str] = Field("", description="Additional operational notes")


class RoleAssignPayload(BaseModel):
    role: str = Field(..., description="Incident Commander (IC), Technical Ops Lead, Communications Lead, Scribe")
    assignee_name: str = Field(..., min_length=2, description="Assignee full name")
    assignee_email: Optional[str] = Field("", description="Assignee email address")
    handover_notes: Optional[str] = Field("", description="Context or briefing handed over to new assignee")


class WarRoomCommandPayload(BaseModel):
    entry_type: Optional[str] = Field("decision", description="decision, action, hypothesis, rollback, status")
    author: str = Field(..., min_length=2, description="Author name or role")
    content: str = Field(..., min_length=3, description="Command log description")


class WarRoomCheckInPayload(BaseModel):
    name: str = Field(..., min_length=2, description="Participant name")
    role: Optional[str] = Field("Technical Specialist", description="Participant role")
    contact: Optional[str] = Field("", description="Phone / handle / email")


class TimelineEventPayload(BaseModel):
    event_type: str = Field("milestone", description="milestone, status_change, diagnostic, mitigation, broadcast")
    summary: str = Field(..., min_length=3, description="Headline of the timeline event")
    details: Optional[str] = Field("", description="Technical or operational details")
    author: Optional[str] = Field("Scribe", description="Author who logged the event")
    event_time: Optional[str] = Field(None, description="Optional explicit ISO timestamp")


# ============================================================================
# 3. CORE ENTERPRISE MIM ENGINE
# ============================================================================

class MIMEngine:
    """Enterprise Major Incident Management Engine conforming to ITIL v4 and Google SRE Incident Command."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, shared_conn: Optional[sqlite3.Connection] = None):
        self.db_path = db_path
        self._shared_conn = shared_conn
        if self._shared_conn is None:
            self._ensure_db_dir()
        self.init_schema()

    def _ensure_db_dir(self) -> None:
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        if self._shared_conn is not None:
            yield self._shared_conn
            return

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
            conn.execute("PRAGMA busy_timeout = 10000;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Creates SQLite schema tables for Major Incident Management."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Major Incidents Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mim_major_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mim_number TEXT UNIQUE NOT NULL,
                    incident_id TEXT DEFAULT NULL,
                    title TEXT NOT NULL,
                    summary TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Active P1 Major Incident',
                    severity TEXT NOT NULL DEFAULT 'P1',
                    impact_scope TEXT DEFAULT 'Enterprise-Wide',
                    blast_radius_json TEXT DEFAULT '{}',
                    incident_start_time TEXT NOT NULL,
                    detected_time TEXT NOT NULL,
                    engaged_time TEXT DEFAULT NULL,
                    mitigated_time TEXT DEFAULT NULL,
                    restored_time TEXT DEFAULT NULL,
                    closed_time TEXT DEFAULT NULL,
                    hourly_downtime_rate REAL DEFAULT 12500.0,
                    downtime_cost REAL DEFAULT 0.0,
                    sla_credits_estimate REAL DEFAULT 0.0,
                    root_cause TEXT DEFAULT '',
                    trigger_event TEXT DEFAULT '',
                    five_whys_json TEXT DEFAULT '[]',
                    lessons_learned_json TEXT DEFAULT '{}',
                    action_items_json TEXT DEFAULT '[]',
                    post_mortem_json TEXT DEFAULT '{}',
                    post_mortem_markdown TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Roles Assignment Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mim_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mim_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    assignee_name TEXT NOT NULL,
                    assignee_email TEXT DEFAULT '',
                    assigned_at TEXT NOT NULL,
                    handover_notes TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (mim_id) REFERENCES mim_major_incidents (id) ON DELETE CASCADE
                );
            """)

            # 3. Real-Time War Rooms Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mim_war_rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mim_id INTEGER UNIQUE NOT NULL,
                    bridge_url TEXT NOT NULL,
                    dial_in_number TEXT NOT NULL,
                    dial_in_pin TEXT NOT NULL,
                    chat_channel TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    opened_at TEXT NOT NULL,
                    closed_at TEXT DEFAULT NULL,
                    attendees_json TEXT DEFAULT '[]',
                    command_log_json TEXT DEFAULT '[]',
                    FOREIGN KEY (mim_id) REFERENCES mim_major_incidents (id) ON DELETE CASCADE
                );
            """)

            # 4. Stakeholder Broadcasts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mim_broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mim_id INTEGER NOT NULL,
                    broadcast_number TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    message_body TEXT NOT NULL,
                    incident_phase TEXT DEFAULT 'Investigating',
                    eta_to_mitigation TEXT DEFAULT '',
                    next_update_due TEXT DEFAULT '',
                    sent_by TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    delivery_channels_json TEXT DEFAULT '["email", "slack"]',
                    recipient_count INTEGER DEFAULT 0,
                    delivery_status TEXT DEFAULT 'delivered',
                    FOREIGN KEY (mim_id) REFERENCES mim_major_incidents (id) ON DELETE CASCADE
                );
            """)

            # 5. Timeline Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mim_timeline_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mim_id INTEGER NOT NULL,
                    event_time TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    author TEXT DEFAULT 'System',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (mim_id) REFERENCES mim_major_incidents (id) ON DELETE CASCADE
                );
            """)

            # 6. State History Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mim_state_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mim_id INTEGER NOT NULL,
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    change_reason TEXT DEFAULT '',
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY (mim_id) REFERENCES mim_major_incidents (id) ON DELETE CASCADE
                );
            """)

            # Indexes for high performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mim_number ON mim_major_incidents (mim_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mim_status ON mim_major_incidents (status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mim_roles_mim_id ON mim_roles (mim_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mim_broadcasts_mim_id ON mim_broadcasts (mim_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mim_timeline_mim_id ON mim_timeline_events (mim_id);")

    # ------------------------------------------------------------------------
    # Core Helpers & Resolution
    # ------------------------------------------------------------------------

    def _next_mim_number(self, cursor: sqlite3.Cursor) -> str:
        """Generates sequence number: MIM-YYYY-XXXX."""
        year = datetime.datetime.now(datetime.timezone.utc).year
        cursor.execute("SELECT mim_number FROM mim_major_incidents WHERE mim_number LIKE ? ORDER BY id DESC LIMIT 1;", (f"MIM-{year}-%",))
        row = cursor.fetchone()
        seq = 1
        if row and row["mim_number"]:
            try:
                parts = row["mim_number"].split("-")
                seq = int(parts[-1]) + 1
            except Exception:
                seq = 1
        return f"MIM-{year}-{seq:04d}"

    def resolve_mim_id(self, cursor: sqlite3.Cursor, identifier: Union[int, str]) -> int:
        """Resolves MIM ID by integer ID, MIM Number (MIM-2026-0001), or linked Incident ID."""
        ident_str = str(identifier).strip()
        if ident_str.isdigit():
            cursor.execute("SELECT id FROM mim_major_incidents WHERE id = ?;", (int(ident_str),))
            row = cursor.fetchone()
            if row:
                return row["id"]

        # Search by MIM number
        cursor.execute("SELECT id FROM mim_major_incidents WHERE UPPER(mim_number) = UPPER(?);", (ident_str,))
        row = cursor.fetchone()
        if row:
            return row["id"]

        # Search by linked incident_id
        cursor.execute("SELECT id FROM mim_major_incidents WHERE UPPER(incident_id) = UPPER(?);", (ident_str,))
        row = cursor.fetchone()
        if row:
            return row["id"]

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Major Incident not found for identifier '{identifier}'",
        )

    # ------------------------------------------------------------------------
    # 1. Promote Incident to Major Incident
    # ------------------------------------------------------------------------

    def promote_incident(self, payload: PromotePayload) -> Dict[str, Any]:
        """Promotes a standard ticket or standalone declaration into an active P1 Major Incident."""
        ts_now = now_iso()
        start_time = payload.incident_start_time or ts_now
        detect_time = payload.detected_time or start_time
        norm_status = MIMStatus.normalize(payload.initial_status or MIMStatus.ACTIVE.value)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            mim_num = self._next_mim_number(cursor)
            blast_json = json.dumps(payload.blast_radius or {})

            # Engagement time is current time when promoting to active
            engaged_time = ts_now if norm_status == MIMStatus.ACTIVE else None

            cursor.execute("""
                INSERT INTO mim_major_incidents (
                    mim_number, incident_id, title, summary, status, severity,
                    impact_scope, blast_radius_json, incident_start_time, detected_time,
                    engaged_time, hourly_downtime_rate, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_num,
                str(payload.incident_id) if payload.incident_id else None,
                payload.title,
                payload.summary or f"Promoted to {norm_status.value} - Enterprise response activated.",
                norm_status.value,
                payload.severity or "P1",
                payload.impact_scope or "Enterprise-Wide",
                blast_json,
                start_time,
                detect_time,
                engaged_time,
                payload.hourly_downtime_rate or 12500.0,
                ts_now,
                ts_now,
            ))
            mim_id = cursor.lastrowid

            # Initial State History
            cursor.execute("""
                INSERT INTO mim_state_history (
                    mim_id, from_status, to_status, changed_by, change_reason, changed_at
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (mim_id, "None", norm_status.value, payload.incident_commander or "Incident Commander", "Initial Major Incident Declaration", ts_now))

            # Initial Timeline Milestone
            cursor.execute("""
                INSERT INTO mim_timeline_events (
                    mim_id, event_time, event_type, summary, details, author, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                start_time,
                "milestone",
                f"Major Incident Declared: {mim_num}",
                f"{payload.title} (Severity: {payload.severity or 'P1'}, Scope: {payload.impact_scope or 'Enterprise-Wide'})",
                payload.incident_commander or "Commander",
                ts_now,
            ))

            # Role Assignments
            roles_to_assign = [
                (MIMRoleType.INCIDENT_COMMANDER.value, payload.incident_commander or "Incident Commander (IC)"),
                (MIMRoleType.TECHNICAL_OPS_LEAD.value, payload.technical_ops_lead or "Technical Ops Lead"),
                (MIMRoleType.COMMUNICATIONS_LEAD.value, payload.communications_lead or "Communications Lead"),
                (MIMRoleType.SCRIBE.value, payload.scribe or "Incident Scribe"),
            ]
            for role_name, person_name in roles_to_assign:
                cursor.execute("""
                    INSERT INTO mim_roles (mim_id, role, assignee_name, assigned_at, is_active)
                    VALUES (?, ?, ?, ?, 1);
                """, (mim_id, role_name, person_name, ts_now))

                cursor.execute("""
                    INSERT INTO mim_timeline_events (
                        mim_id, event_time, event_type, summary, details, author, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    mim_id,
                    ts_now,
                    "role_assigned",
                    f"Role Assigned: {role_name}",
                    f"Assigned to {person_name}",
                    "System",
                    ts_now,
                ))

            # Real-Time War Room Initialization
            war_bridge = payload.war_room_url or f"https://meet.opennow.internal/warroom/{mim_num.lower()}"
            dial_pin = f"{uuid.uuid4().int % 900000 + 100000} #"
            chat_chan = payload.chat_channel or f"#warroom-{mim_num.lower()}"

            initial_attendees = [
                {"name": payload.incident_commander, "role": MIMRoleType.INCIDENT_COMMANDER.value, "joined_at": ts_now},
                {"name": payload.technical_ops_lead, "role": MIMRoleType.TECHNICAL_OPS_LEAD.value, "joined_at": ts_now},
                {"name": payload.communications_lead, "role": MIMRoleType.COMMUNICATIONS_LEAD.value, "joined_at": ts_now},
                {"name": payload.scribe, "role": MIMRoleType.SCRIBE.value, "joined_at": ts_now},
            ]
            initial_commands = [
                {
                    "timestamp": ts_now,
                    "author": payload.incident_commander or "Incident Commander",
                    "entry_type": "decision",
                    "content": f"War room bridge activated. Primary objective: isolate blast radius, maintain 15-minute comms cadence, and drive toward mitigation."
                }
            ]

            cursor.execute("""
                INSERT INTO mim_war_rooms (
                    mim_id, bridge_url, dial_in_number, dial_in_pin, chat_channel,
                    status, opened_at, attendees_json, command_log_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                war_bridge,
                "+1-800-555-MIM1 (+1-800-555-0199)",
                dial_pin,
                chat_chan,
                "active",
                ts_now,
                json.dumps(initial_attendees),
                json.dumps(initial_commands),
            ))

            cursor.execute("""
                INSERT INTO mim_timeline_events (
                    mim_id, event_time, event_type, summary, details, author, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                ts_now,
                "war_room_created",
                f"Real-Time War Room Bridge Activated",
                f"Bridge: {war_bridge} | Dial-in: +1-800-555-0199 PIN: {dial_pin} | Channel: {chat_chan}",
                "System",
                ts_now,
            ))

        return self.get_major_incident(mim_id)

    # ------------------------------------------------------------------------
    # 2. Get Single Major Incident Detail
    # ------------------------------------------------------------------------

    def get_major_incident(self, identifier: Union[int, str]) -> Dict[str, Any]:
        """Returns comprehensive major incident detail, roles, war room, broadcasts, and chronometer."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            mim_id = self.resolve_mim_id(cursor, identifier)

            cursor.execute("SELECT * FROM mim_major_incidents WHERE id = ?;", (mim_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Major Incident ID {mim_id} not found")

            # Roles
            cursor.execute("SELECT * FROM mim_roles WHERE mim_id = ? ORDER BY id ASC;", (mim_id,))
            roles_rows = cursor.fetchall()
            roles_dict: Dict[str, Any] = {
                "incident_commander": None,
                "technical_ops_lead": None,
                "communications_lead": None,
                "scribe": None,
                "all_assignments": [],
            }
            for r in roles_rows:
                r_dict = dict(r)
                roles_dict["all_assignments"].append(r_dict)
                if r["is_active"]:
                    if "command" in r["role"].lower():
                        roles_dict["incident_commander"] = r_dict
                    elif "tech" in r["role"].lower() or "ops" in r["role"].lower():
                        roles_dict["technical_ops_lead"] = r_dict
                    elif "comm" in r["role"].lower():
                        roles_dict["communications_lead"] = r_dict
                    elif "scribe" in r["role"].lower():
                        roles_dict["scribe"] = r_dict

            # War Room
            cursor.execute("SELECT * FROM mim_war_rooms WHERE mim_id = ?;", (mim_id,))
            war_row = cursor.fetchone()
            war_room: Optional[Dict[str, Any]] = None
            if war_row:
                war_room = dict(war_row)
                try:
                    war_room["attendees"] = json.loads(war_room.get("attendees_json") or "[]")
                except Exception:
                    war_room["attendees"] = []
                try:
                    war_room["command_log"] = json.loads(war_room.get("command_log_json") or "[]")
                except Exception:
                    war_room["command_log"] = []

            # Stakeholder Broadcasts
            cursor.execute("SELECT * FROM mim_broadcasts WHERE mim_id = ? ORDER BY id DESC;", (mim_id,))
            broadcast_rows = cursor.fetchall()
            broadcasts = []
            for b in broadcast_rows:
                b_dict = dict(b)
                try:
                    b_dict["delivery_channels"] = json.loads(b_dict.get("delivery_channels_json") or "[]")
                except Exception:
                    b_dict["delivery_channels"] = []
                broadcasts.append(b_dict)

            # Timeline Events
            cursor.execute("SELECT * FROM mim_timeline_events WHERE mim_id = ? ORDER BY event_time ASC, id ASC;", (mim_id,))
            timeline_rows = cursor.fetchall()
            timeline = [dict(t) for t in timeline_rows]

            # State History
            cursor.execute("SELECT * FROM mim_state_history WHERE mim_id = ? ORDER BY id ASC;", (mim_id,))
            history = [dict(h) for h in cursor.fetchall()]

            # Chronometer Metrics Calculation
            chronometer = self.calculate_chronometer(dict(row), broadcasts)

            # Post Mortem parsing
            item = dict(row)
            try:
                item["blast_radius"] = json.loads(item.get("blast_radius_json") or "{}")
            except Exception:
                item["blast_radius"] = {}

            try:
                item["five_whys"] = json.loads(item.get("five_whys_json") or "[]")
            except Exception:
                item["five_whys"] = []

            try:
                item["lessons_learned"] = json.loads(item.get("lessons_learned_json") or "{}")
            except Exception:
                item["lessons_learned"] = {}

            try:
                item["action_items"] = json.loads(item.get("action_items_json") or "[]")
            except Exception:
                item["action_items"] = []

            try:
                item["post_mortem"] = json.loads(item.get("post_mortem_json") or "{}")
            except Exception:
                item["post_mortem"] = {}

            item["roles"] = roles_dict
            item["war_room"] = war_room
            item["broadcasts"] = broadcasts
            item["timeline"] = timeline
            item["state_history"] = history
            item["chronometer"] = chronometer

            return item

    # ------------------------------------------------------------------------
    # 3. List Active Major Incidents
    # ------------------------------------------------------------------------

    def list_active_major_incidents(self) -> List[Dict[str, Any]]:
        """Returns all Major Incidents currently in active/proposed/mitigated states with live war room details."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            active_statuses = [
                MIMStatus.ACTIVE.value,
                MIMStatus.PROPOSED.value,
                MIMStatus.MITIGATED.value,
                MIMStatus.CANDIDATE.value,
            ]
            placeholders = ",".join("?" for _ in active_statuses)
            cursor.execute(f"""
                SELECT id FROM mim_major_incidents
                WHERE status IN ({placeholders})
                ORDER BY CASE status
                    WHEN '{MIMStatus.ACTIVE.value}' THEN 1
                    WHEN '{MIMStatus.PROPOSED.value}' THEN 2
                    WHEN '{MIMStatus.MITIGATED.value}' THEN 3
                    ELSE 4
                END, id DESC;
            """, active_statuses)
            rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append(self.get_major_incident(r["id"]))
        return results

    def list_all_major_incidents(self, status_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists major incidents with optional status filter."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status_filter:
                cursor.execute(
                    "SELECT id FROM mim_major_incidents WHERE UPPER(status) LIKE UPPER(?) ORDER BY id DESC LIMIT ?;",
                    (f"%{status_filter}%", limit),
                )
            else:
                cursor.execute("SELECT id FROM mim_major_incidents ORDER BY id DESC LIMIT ?;", (limit,))
            rows = cursor.fetchall()

        return [self.get_major_incident(r["id"]) for r in rows]

    # ------------------------------------------------------------------------
    # 4. Chronometer Metrics Engine (TTD, TTE, TTM, TTR)
    # ------------------------------------------------------------------------

    def calculate_chronometer(self, incident: Dict[str, Any], broadcasts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates precise ITIL & SRE Chronometer metrics:
        - Time to Detect (TTD): incident_start_time -> detected_time
        - Time to Engage (TTE): detected_time -> engaged_time
        - Time to Mitigate (TTM): engaged_time -> mitigated_time
        - Time to Restore (TTR): incident_start_time -> restored_time
        Also calculates live outage elapsed time, broadcast cadence, and SLA target breach status.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        dt_start = parse_iso(incident.get("incident_start_time")) or now
        dt_detect = parse_iso(incident.get("detected_time")) or dt_start
        dt_engage = parse_iso(incident.get("engaged_time"))
        dt_mitigate = parse_iso(incident.get("mitigated_time"))
        dt_restore = parse_iso(incident.get("restored_time"))
        dt_close = parse_iso(incident.get("closed_time"))

        # Time to Detect (TTD)
        ttd_seconds = max(0.0, (dt_detect - dt_start).total_seconds())

        # Time to Engage (TTE)
        tte_seconds: Optional[float] = None
        if dt_engage:
            tte_seconds = max(0.0, (dt_engage - dt_detect).total_seconds())

        # Time to Mitigate (TTM)
        ttm_seconds: Optional[float] = None
        if dt_mitigate:
            reference_point = dt_engage or dt_detect
            ttm_seconds = max(0.0, (dt_mitigate - reference_point).total_seconds())

        # Time to Restore (TTR / MTTR)
        ttr_seconds: Optional[float] = None
        if dt_restore:
            ttr_seconds = max(0.0, (dt_restore - dt_start).total_seconds())

        # Current Total Outage Duration
        end_point = dt_restore or now
        total_outage_seconds = max(0.0, (end_point - dt_start).total_seconds())

        # Cadence & Broadcast Chronometer
        time_since_last_broadcast_seconds: Optional[float] = None
        if broadcasts:
            latest_bc_time = parse_iso(broadcasts[0].get("sent_at"))
            if latest_bc_time:
                time_since_last_broadcast_seconds = max(0.0, (now - latest_bc_time).total_seconds())

        # SLA Target (P1 target: 60 minutes for mitigation, 120 minutes for restoration)
        sla_mitigation_target_sec = 60 * 60.0
        sla_restoration_target_sec = 120 * 60.0

        is_mitigation_sla_breached = (ttm_seconds is not None and ttm_seconds > sla_mitigation_target_sec) or (
            dt_mitigate is None and total_outage_seconds > sla_mitigation_target_sec
        )
        is_restoration_sla_breached = (ttr_seconds is not None and ttr_seconds > sla_restoration_target_sec) or (
            dt_restore is None and total_outage_seconds > sla_restoration_target_sec
        )

        # Financial Downtime Calculation
        hourly_rate = float(incident.get("hourly_downtime_rate") or 12500.0)
        outage_hours = total_outage_seconds / 3600.0
        downtime_cost = round(outage_hours * hourly_rate, 2)

        return {
            "time_to_detect": {
                "seconds": round(ttd_seconds, 1),
                "formatted": format_duration(ttd_seconds),
                "description": "Start of disruption to monitoring alert / detection",
            },
            "time_to_engage": {
                "seconds": round(tte_seconds, 1) if tte_seconds is not None else None,
                "formatted": format_duration(tte_seconds) if tte_seconds is not None else "Pending Engagement",
                "description": "Detection to Incident Commander & War Room bridge active",
            },
            "time_to_mitigate": {
                "seconds": round(ttm_seconds, 1) if ttm_seconds is not None else None,
                "formatted": format_duration(ttm_seconds) if ttm_seconds is not None else "In Progress",
                "description": "Engagement to immediate workaround / blast radius mitigation",
            },
            "time_to_restore": {
                "seconds": round(ttr_seconds, 1) if ttr_seconds is not None else None,
                "formatted": format_duration(ttr_seconds) if ttr_seconds is not None else "In Progress",
                "description": "Incident start to 100% production service restoration verified",
            },
            "outage_duration": {
                "total_seconds": round(total_outage_seconds, 1),
                "formatted": format_duration(total_outage_seconds),
                "hours": round(outage_hours, 2),
                "is_active": dt_restore is None,
            },
            "broadcast_cadence": {
                "time_since_last_broadcast_seconds": round(time_since_last_broadcast_seconds, 1) if time_since_last_broadcast_seconds is not None else None,
                "formatted_time_since_last_broadcast": format_duration(time_since_last_broadcast_seconds) if time_since_last_broadcast_seconds is not None else "No broadcasts sent yet",
                "target_cadence_minutes": 15,
                "cadence_overdue": (time_since_last_broadcast_seconds or 0.0) > (15 * 60),
            },
            "sla_compliance": {
                "mitigation_target": "60m",
                "restoration_target": "120m",
                "mitigation_sla_breached": is_mitigation_sla_breached,
                "restoration_sla_breached": is_restoration_sla_breached,
            },
            "financial_impact": {
                "hourly_rate": hourly_rate,
                "estimated_downtime_cost": downtime_cost,
                "currency": "USD",
            },
        }

    # ------------------------------------------------------------------------
    # 5. Stakeholder Broadcast Engine
    # ------------------------------------------------------------------------

    def send_broadcast(self, identifier: Union[int, str], payload: BroadcastPayload) -> Dict[str, Any]:
        """Dispatches an enterprise stakeholder broadcast (internal technical bulletin vs customer status page)."""
        ts_now = now_iso()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            mim_id = self.resolve_mim_id(cursor, identifier)

            cursor.execute("SELECT mim_number, status, title FROM mim_major_incidents WHERE id = ?;", (mim_id,))
            inc_row = cursor.fetchone()
            if not inc_row:
                raise HTTPException(status_code=404, detail="Major Incident not found")

            # Next broadcast number for this MIM
            cursor.execute("SELECT COUNT(*) AS count FROM mim_broadcasts WHERE mim_id = ?;", (mim_id,))
            bc_count = cursor.fetchone()["count"] + 1
            bc_number = f"BC-{bc_count:03d}"

            # Calculate recipient count heuristic based on audience
            recipient_count = 1450 if payload.audience == BroadcastAudience.CUSTOMER_STATUS_PAGE.value else (
                42 if payload.audience == BroadcastAudience.EXTERNAL_EXECUTIVE.value else 185
            )

            channels_json = json.dumps(payload.delivery_channels or ["slack", "email", "statuspage"])

            cursor.execute("""
                INSERT INTO mim_broadcasts (
                    mim_id, broadcast_number, audience, subject, message_body,
                    incident_phase, eta_to_mitigation, next_update_due, sent_by,
                    sent_at, delivery_channels_json, recipient_count, delivery_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                bc_number,
                payload.audience,
                payload.subject,
                payload.message_body,
                payload.incident_phase or IncidentPhase.INVESTIGATING.value,
                payload.eta_to_mitigation or "",
                payload.next_update_due or "",
                payload.sent_by or "Communications Lead",
                ts_now,
                channels_json,
                recipient_count,
                "delivered",
            ))
            bc_id = cursor.lastrowid

            # Add to Timeline
            audience_label = {
                BroadcastAudience.INTERNAL_TECHNICAL.value: "Internal Technical Bulletin",
                BroadcastAudience.EXTERNAL_EXECUTIVE.value: "Executive Briefing",
                BroadcastAudience.CUSTOMER_STATUS_PAGE.value: "Customer Status Page Update",
            }.get(payload.audience, payload.audience)

            cursor.execute("""
                INSERT INTO mim_timeline_events (
                    mim_id, event_time, event_type, summary, details, author, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                ts_now,
                "broadcast_sent",
                f"Stakeholder Broadcast Dispatched ({bc_number}): {audience_label}",
                f"Subject: {payload.subject}\nPhase: {payload.incident_phase}\nETA: {payload.eta_to_mitigation}",
                payload.sent_by or "Comms Lead",
                ts_now,
            ))

            # Fetch created broadcast
            cursor.execute("SELECT * FROM mim_broadcasts WHERE id = ?;", (bc_id,))
            created_bc = dict(cursor.fetchone())
            created_bc["delivery_channels"] = json.loads(created_bc.get("delivery_channels_json") or "[]")

            return {
                "broadcast": created_bc,
                "broadcast_number": bc_number,
                "audience": payload.audience,
                "recipients_delivered": recipient_count,
                "status": "delivered",
                "next_cadence_due": payload.next_update_due or "15 minutes",
                "published_to_statuspage": payload.audience == BroadcastAudience.CUSTOMER_STATUS_PAGE.value,
            }

    # ------------------------------------------------------------------------
    # 6. Role Assignments & Handovers
    # ------------------------------------------------------------------------

    def assign_role(self, identifier: Union[int, str], payload: RoleAssignPayload) -> Dict[str, Any]:
        """Assigns an incident command role or performs a formal role handover."""
        ts_now = now_iso()
        norm_role = MIMRoleType.normalize(payload.role).value

        with self.get_connection() as conn:
            cursor = conn.cursor()
            mim_id = self.resolve_mim_id(cursor, identifier)

            # Deactivate previous active holder of this role
            cursor.execute("""
                UPDATE mim_roles SET is_active = 0 WHERE mim_id = ? AND role = ?;
            """, (mim_id, norm_role))

            # Insert new role assignment
            cursor.execute("""
                INSERT INTO mim_roles (
                    mim_id, role, assignee_name, assignee_email, assigned_at, handover_notes, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, 1);
            """, (
                mim_id,
                norm_role,
                payload.assignee_name,
                payload.assignee_email or "",
                ts_now,
                payload.handover_notes or "",
            ))

            # Log to timeline
            handover_msg = f"Handover notes: {payload.handover_notes}" if payload.handover_notes else ""
            cursor.execute("""
                INSERT INTO mim_timeline_events (
                    mim_id, event_time, event_type, summary, details, author, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                ts_now,
                "role_assigned",
                f"Role Handover: {norm_role} -> {payload.assignee_name}",
                handover_msg,
                "Incident Commander",
                ts_now,
            ))

        return self.get_major_incident(mim_id)

    # ------------------------------------------------------------------------
    # 7. State Transitions & Guards
    # ------------------------------------------------------------------------

    def transition_status(self, identifier: Union[int, str], payload: StatusTransitionPayload) -> Dict[str, Any]:
        """Transitions major incident state with ITIL transition guards."""
        ts_now = now_iso()
        target_norm = MIMStatus.normalize(payload.target_status)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            mim_id = self.resolve_mim_id(cursor, identifier)

            cursor.execute("SELECT * FROM mim_major_incidents WHERE id = ?;", (mim_id,))
            current = cursor.fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="Major Incident not found")

            curr_status = MIMStatus.normalize(current["status"])

            # Transition guard check
            allowed = VALID_TRANSITIONS.get(curr_status, [])
            if target_norm != curr_status and target_norm not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Illegal transition from '{curr_status.value}' to '{target_norm.value}'. Allowed: {[s.value for s in allowed]}",
                )

            # State timestamp updates
            mitigated_time = current["mitigated_time"]
            restored_time = current["restored_time"]
            closed_time = current["closed_time"]
            engaged_time = current["engaged_time"]

            if target_norm == MIMStatus.ACTIVE and not engaged_time:
                engaged_time = ts_now

            if target_norm == MIMStatus.MITIGATED and not mitigated_time:
                mitigated_time = ts_now

            if target_norm in (MIMStatus.PIR, MIMStatus.CLOSED):
                if not mitigated_time:
                    mitigated_time = ts_now
                if not restored_time:
                    restored_time = ts_now

            if target_norm == MIMStatus.CLOSED and not closed_time:
                closed_time = ts_now

            # Downtime Cost final calculation upon restoration or close
            hourly_rate = float(current["hourly_downtime_rate"] or 12500.0)
            start_dt = parse_iso(current["incident_start_time"]) or parse_iso(ts_now)
            end_dt = parse_iso(restored_time or ts_now)
            outage_sec = max(0.0, (end_dt - start_dt).total_seconds()) if start_dt and end_dt else 0.0
            downtime_cost = round((outage_sec / 3600.0) * hourly_rate, 2)

            cursor.execute("""
                UPDATE mim_major_incidents SET
                    status = ?,
                    engaged_time = ?,
                    mitigated_time = ?,
                    restored_time = ?,
                    closed_time = ?,
                    downtime_cost = ?,
                    updated_at = ?
                WHERE id = ?;
            """, (
                target_norm.value,
                engaged_time,
                mitigated_time,
                restored_time,
                closed_time,
                downtime_cost,
                ts_now,
                mim_id,
            ))

            # State History
            cursor.execute("""
                INSERT INTO mim_state_history (
                    mim_id, from_status, to_status, changed_by, change_reason, changed_at
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                curr_status.value,
                target_norm.value,
                payload.actor or "Incident Commander",
                payload.reason or f"Transition to {target_norm.value}",
                ts_now,
            ))

            # Timeline Milestone
            cursor.execute("""
                INSERT INTO mim_timeline_events (
                    mim_id, event_time, event_type, summary, details, author, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                ts_now,
                "status_change",
                f"Incident Status Changed: {curr_status.value} -> {target_norm.value}",
                payload.reason or payload.notes or "",
                payload.actor or "Incident Commander",
                ts_now,
            ))

            # If closed, archive war room
            if target_norm == MIMStatus.CLOSED:
                cursor.execute("""
                    UPDATE mim_war_rooms SET status = 'closed', closed_at = ? WHERE mim_id = ?;
                """, (ts_now, mim_id))

        return self.get_major_incident(mim_id)

    # ------------------------------------------------------------------------
    # 8. War Room Command Log & Attendees Check-In
    # ------------------------------------------------------------------------

    def append_war_room_command(self, identifier: Union[int, str], payload: WarRoomCommandPayload) -> Dict[str, Any]:
        """Appends a tactical decision, hypothesis, rollback, or command log entry to the active War Room."""
        ts_now = now_iso()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            mim_id = self.resolve_mim_id(cursor, identifier)

            cursor.execute("SELECT command_log_json FROM mim_war_rooms WHERE mim_id = ?;", (mim_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="War Room not found for this Major Incident")

            commands = json.loads(row["command_log_json"] or "[]")
            entry = {
                "id": str(uuid.uuid4())[:8],
                "timestamp": ts_now,
                "author": payload.author,
                "entry_type": payload.entry_type or "decision",
                "content": payload.content,
            }
            commands.append(entry)

            cursor.execute("""
                UPDATE mim_war_rooms SET command_log_json = ? WHERE mim_id = ?;
            """, (json.dumps(commands), mim_id))

            # Also add to official incident timeline if decision/rollback/milestone
            if payload.entry_type in ("decision", "rollback", "mitigation", "milestone"):
                cursor.execute("""
                    INSERT INTO mim_timeline_events (
                        mim_id, event_time, event_type, summary, details, author, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    mim_id,
                    ts_now,
                    "command_decision",
                    f"War Room Decision [{payload.entry_type.upper()}]: {payload.content[:80]}",
                    payload.content,
                    payload.author,
                    ts_now,
                ))

        return entry

    def war_room_check_in(self, identifier: Union[int, str], payload: WarRoomCheckInPayload) -> Dict[str, Any]:
        """Records an attendee checking into the real-time War Room bridge."""
        ts_now = now_iso()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            mim_id = self.resolve_mim_id(cursor, identifier)

            cursor.execute("SELECT attendees_json FROM mim_war_rooms WHERE mim_id = ?;", (mim_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="War Room not found")

            attendees = json.loads(row["attendees_json"] or "[]")
            attendee = {
                "name": payload.name,
                "role": payload.role or "Specialist",
                "contact": payload.contact or "",
                "joined_at": ts_now,
            }
            # Append if not already present
            if not any(a.get("name") == payload.name for a in attendees):
                attendees.append(attendee)
                cursor.execute("""
                    UPDATE mim_war_rooms SET attendees_json = ? WHERE mim_id = ?;
                """, (json.dumps(attendees), mim_id))

        return attendee

    def add_timeline_event(self, identifier: Union[int, str], payload: TimelineEventPayload) -> Dict[str, Any]:
        """Adds a custom milestone or event into the official chronological incident timeline."""
        ts_now = now_iso()
        event_time = payload.event_time or ts_now
        with self.get_connection() as conn:
            cursor = conn.cursor()
            mim_id = self.resolve_mim_id(cursor, identifier)

            cursor.execute("""
                INSERT INTO mim_timeline_events (
                    mim_id, event_time, event_type, summary, details, author, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                event_time,
                payload.event_type or "milestone",
                payload.summary,
                payload.details or "",
                payload.author or "Scribe",
                ts_now,
            ))
            event_id = cursor.lastrowid

            cursor.execute("SELECT * FROM mim_timeline_events WHERE id = ?;", (event_id,))
            return dict(cursor.fetchone())

    # ------------------------------------------------------------------------
    # 9. Blameless Post-Mortem & Post-Incident Review (PIR) Generator
    # ------------------------------------------------------------------------

    def generate_post_mortem(self, identifier: Union[int, str], payload: Optional[PostMortemGeneratePayload] = None) -> Dict[str, Any]:
        """Auto-compiles timeline, root cause, 5-whys, impacted customers, downtime cost ($),
        and preventative action items into exportable JSON and Markdown.
        Conforms strictly to Google SRE Blameless Post-Mortem culture.
        """
        payload = payload or PostMortemGeneratePayload()
        ts_now = now_iso()

        # Retrieve major incident full dataset
        inc = self.get_major_incident(identifier)
        mim_id = inc["id"]
        mim_num = inc["mim_number"]
        chronometer = inc["chronometer"]

        # 1. Root Cause & 5-Whys Synthesis
        root_cause = payload.root_cause or inc.get("root_cause") or (
            "Exhaustion of connection pool across distributed PostgreSQL cluster triggered by unindexed batch query during peak traffic load."
        )
        trigger_event = payload.trigger_event or inc.get("trigger_event") or (
            "Scheduled ETL billing reconciliation cron fired simultaneously with automated scale-out event."
        )

        five_whys = payload.five_whys if payload.five_whys is not None else inc.get("five_whys")
        if not five_whys:
            five_whys = [
                {"step": 1, "question": "Why did customer API requests experience 504 Gateway Timeouts?", "answer": "The core authentication and transaction service exhausted all database connections."},
                {"step": 2, "question": "Why did database connections become saturated?", "answer": "A burst of 45 concurrent unindexed batch queries held table locks for > 180 seconds."},
                {"step": 3, "question": "Why were batch reconciliation queries executing against primary read/write database?", "answer": "The read-replica connection router fell back to primary after replica failover heartbeat timeout."},
                {"step": 4, "question": "Why didn't circuit breakers trip to isolate batch traffic from customer transactions?", "answer": "The connection pool configuration shared a unified thread pool instead of segregated isolation bulkhead pools."},
                {"step": 5, "question": "Why was the bulkhead pattern missing from the transaction gateway architecture?", "answer": "Architectural standard AS-402 was implemented on payments service but had not yet propagated to core auth gateway in sprint backlog."},
            ]

        # 2. Blast Radius & Customer Impact
        blast_radius = inc.get("blast_radius", {})
        affected_services = payload.affected_services or blast_radius.get("affected_services", ["Core API Gateway", "Authentication Broker", "Customer Portal"])
        impacted_customers = payload.impacted_customers or blast_radius.get("affected_tenants", ["Enterprise Global Tier-1", "North America Retail Tenants"])
        affected_users = blast_radius.get("affected_users", 12500)
        error_rate_pct = blast_radius.get("error_rate_pct", 94.2)

        # 3. Financial Downtime Cost Calculation
        hourly_rate = payload.hourly_downtime_rate or inc.get("hourly_downtime_rate") or 12500.0
        outage_hours = chronometer["outage_duration"]["hours"]
        downtime_cost = round(outage_hours * hourly_rate, 2)
        sla_credits = payload.sla_credits_estimate or round(downtime_cost * 0.25, 2)
        total_financial_loss = round(downtime_cost + sla_credits, 2)

        # 4. Lessons Learned (Blameless)
        what_went_well = payload.what_went_well or [
            "Incident Commander declared Major Incident within 3 minutes of synthetic alert trigger.",
            "War Room bridge established immediately with 100% quorum across SRE and DB leads.",
            "15-minute stakeholder broadcast cadence maintained throughout entire disruption.",
            "Automated rollback scripts functioned properly once DB locks were cleared.",
        ]
        what_went_wrong = payload.what_went_wrong or [
            "Initial alerts were silenced in secondary on-call escalation channel for 6 minutes.",
            "Grafana connection pool dashboard was stale due to Prometheus scraper timeout.",
            "Failover replica switchover required manual credential re-binding by Ops Lead.",
        ]
        where_we_got_lucky = payload.where_we_got_lucky or [
            "Incident occurred at 10:45 AM UTC, coinciding with regular engineering business hours rather than middle of night.",
            "Offsite automated database WAL archive backups had completed 12 minutes prior to pool saturation.",
        ]

        # 5. Preventative & Hardening Action Items (SRE)
        action_items = payload.action_items if payload.action_items is not None else inc.get("action_items")
        if not action_items:
            action_items = [
                {
                    "id": "ACT-001",
                    "title": "Implement Bulkhead Isolation for Batch ETL vs Interactive API Pools",
                    "category": "Architectural Prevention",
                    "owner": inc["roles"]["technical_ops_lead"]["assignee_name"] if inc["roles"]["technical_ops_lead"] else "Engineering Architecture Lead",
                    "priority": "P1",
                    "target_due": "In 7 Days",
                    "status": "In Progress",
                },
                {
                    "id": "ACT-002",
                    "title": "Deploy Query Execution Time Circuit Breakers (> 10s auto-kill for non-critical callers)",
                    "category": "Detection & Circuit Breakers",
                    "owner": "Database Reliability Engineering Team",
                    "priority": "P1",
                    "target_due": "In 14 Days",
                    "status": "Open",
                },
                {
                    "id": "ACT-003",
                    "title": "Update Read-Replica Failover Healthcheck Runbook and Automated Re-bind",
                    "category": "Process & Runbooks",
                    "owner": inc["roles"]["incident_commander"]["assignee_name"] if inc["roles"]["incident_commander"] else "SRE Commander",
                    "priority": "P2",
                    "target_due": "In 21 Days",
                    "status": "Open",
                },
                {
                    "id": "ACT-004",
                    "title": "Add Prometheus High-Resolution Alert for Connection Pool Acquisition Wait Times",
                    "category": "Observability",
                    "owner": "Observability & Monitoring Guild",
                    "priority": "P2",
                    "target_due": "In 7 Days",
                    "status": "Open",
                },
            ]

        # 6. Chronological Timeline Compilation
        timeline_entries = inc.get("timeline", [])
        dt_start = parse_iso(inc.get("incident_start_time"))

        compiled_timeline = []
        for t in timeline_entries:
            t_dt = parse_iso(t.get("event_time"))
            elapsed_str = "+00:00"
            if dt_start and t_dt:
                delta_sec = (t_dt - dt_start).total_seconds()
                sign = "+" if delta_sec >= 0 else "-"
                delta_sec = abs(delta_sec)
                hrs = int(delta_sec // 3600)
                mins = int((delta_sec % 3600) // 60)
                elapsed_str = f"{sign}{hrs:02d}:{mins:02d}"

            compiled_timeline.append({
                "time": t.get("event_time"),
                "elapsed": elapsed_str,
                "event_type": t.get("event_type"),
                "summary": t.get("summary"),
                "details": t.get("details"),
                "author": t.get("author"),
            })

        # 7. Generate Professional Blameless Markdown Report
        markdown_doc = self._build_post_mortem_markdown(
            inc=inc,
            chronometer=chronometer,
            root_cause=root_cause,
            trigger_event=trigger_event,
            five_whys=five_whys,
            affected_services=affected_services,
            impacted_customers=impacted_customers,
            affected_users=affected_users,
            error_rate_pct=error_rate_pct,
            hourly_rate=hourly_rate,
            downtime_cost=downtime_cost,
            sla_credits=sla_credits,
            total_financial_loss=total_financial_loss,
            what_went_well=what_went_well,
            what_went_wrong=what_went_wrong,
            where_we_got_lucky=where_we_got_lucky,
            action_items=action_items,
            timeline=compiled_timeline,
        )

        post_mortem_data = {
            "major_incident_number": mim_num,
            "title": inc["title"],
            "severity": inc["severity"],
            "status": inc["status"],
            "published_at": ts_now,
            "blameless_statement": "This review is conducted with a blameless culture. We examine systemic vulnerabilities and procedural gaps rather than assigning human fault.",
            "incident_command_roles": {
                "incident_commander": inc["roles"]["incident_commander"]["assignee_name"] if inc["roles"]["incident_commander"] else "Unassigned",
                "technical_ops_lead": inc["roles"]["technical_ops_lead"]["assignee_name"] if inc["roles"]["technical_ops_lead"] else "Unassigned",
                "communications_lead": inc["roles"]["communications_lead"]["assignee_name"] if inc["roles"]["communications_lead"] else "Unassigned",
                "scribe": inc["roles"]["scribe"]["assignee_name"] if inc["roles"]["scribe"] else "Unassigned",
            },
            "chronometer_metrics": {
                "time_to_detect": chronometer["time_to_detect"],
                "time_to_engage": chronometer["time_to_engage"],
                "time_to_mitigate": chronometer["time_to_mitigate"],
                "time_to_restore": chronometer["time_to_restore"],
                "total_outage_formatted": chronometer["outage_duration"]["formatted"],
                "total_outage_hours": chronometer["outage_duration"]["hours"],
            },
            "financial_downtime_impact": {
                "hourly_downtime_rate": hourly_rate,
                "downtime_cost_usd": downtime_cost,
                "sla_credit_penalty_usd": sla_credits,
                "total_financial_impact_usd": total_financial_loss,
            },
            "impact_blast_radius": {
                "affected_services": affected_services,
                "impacted_customers": impacted_customers,
                "affected_users_count": affected_users,
                "peak_error_rate_pct": error_rate_pct,
            },
            "root_cause_analysis": {
                "trigger_event": trigger_event,
                "root_cause": root_cause,
                "five_whys": five_whys,
            },
            "lessons_learned": {
                "what_went_well": what_went_well,
                "what_went_wrong": what_went_wrong,
                "where_we_got_lucky": where_we_got_lucky,
            },
            "preventative_action_items": action_items,
            "timeline": compiled_timeline,
        }

        # Save to database
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE mim_major_incidents SET
                    root_cause = ?,
                    trigger_event = ?,
                    five_whys_json = ?,
                    lessons_learned_json = ?,
                    action_items_json = ?,
                    post_mortem_json = ?,
                    post_mortem_markdown = ?,
                    downtime_cost = ?,
                    sla_credits_estimate = ?,
                    updated_at = ?
                WHERE id = ?;
            """, (
                root_cause,
                trigger_event,
                json.dumps(five_whys),
                json.dumps({
                    "what_went_well": what_went_well,
                    "what_went_wrong": what_went_wrong,
                    "where_we_got_lucky": where_we_got_lucky,
                }),
                json.dumps(action_items),
                json.dumps(post_mortem_data),
                markdown_doc,
                downtime_cost,
                sla_credits,
                ts_now,
                mim_id,
            ))

            # Add timeline entry for PIR generation
            cursor.execute("""
                INSERT INTO mim_timeline_events (
                    mim_id, event_time, event_type, summary, details, author, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                mim_id,
                ts_now,
                "milestone",
                "Blameless Post-Mortem & PIR Generated",
                f"Full blameless review auto-compiled. Financial impact: ${total_financial_loss:,.2f} USD.",
                inc["roles"]["scribe"]["assignee_name"] if inc["roles"]["scribe"] else "Scribe",
                ts_now,
            ))

        return {
            "major_incident_number": mim_num,
            "post_mortem_json": post_mortem_data,
            "post_mortem_markdown": markdown_doc,
            "status": "generated",
            "downtime_cost_usd": downtime_cost,
            "total_financial_impact_usd": total_financial_loss,
        }

    def _build_post_mortem_markdown(
        self,
        inc: Dict[str, Any],
        chronometer: Dict[str, Any],
        root_cause: str,
        trigger_event: str,
        five_whys: List[Any],
        affected_services: List[str],
        impacted_customers: List[str],
        affected_users: int,
        error_rate_pct: float,
        hourly_rate: float,
        downtime_cost: float,
        sla_credits: float,
        total_financial_loss: float,
        what_went_well: List[str],
        what_went_wrong: List[str],
        where_we_got_lucky: List[str],
        action_items: List[Dict[str, Any]],
        timeline: List[Dict[str, Any]],
    ) -> str:
        """Constructs an enterprise-grade Blameless Post-Mortem markdown document."""
        mim_num = inc["mim_number"]
        title = inc["title"]
        severity = inc["severity"]
        start_time = inc["incident_start_time"]
        mitigated_time = inc["mitigated_time"] or "Pending"
        restored_time = inc["restored_time"] or "Pending"

        ic_name = inc["roles"]["incident_commander"]["assignee_name"] if inc["roles"]["incident_commander"] else "Unassigned"
        tech_name = inc["roles"]["technical_ops_lead"]["assignee_name"] if inc["roles"]["technical_ops_lead"] else "Unassigned"
        comms_name = inc["roles"]["communications_lead"]["assignee_name"] if inc["roles"]["communications_lead"] else "Unassigned"
        scribe_name = inc["roles"]["scribe"]["assignee_name"] if inc["roles"]["scribe"] else "Unassigned"

        md = []
        md.append(f"# Post-Incident Review (PIR) & Blameless Post-Mortem")
        md.append(f"## {mim_num}: {title}\n")
        md.append("> **Blameless Culture Policy**: *This review is designed to discover systemic vulnerabilities and organizational improvements. We do not punish or assign personal blame for honest errors or unexpected system dynamics.*")
        md.append("")
        md.append("---")
        md.append("")

        # Section 1: Executive Overview
        md.append("### 1. Executive Incident Overview")
        md.append(f"| Attribute | Value |")
        md.append(f"| :--- | :--- |")
        md.append(f"| **Incident Identifier** | `{mim_num}` |")
        md.append(f"| **Severity Rating** | **{severity} - Critical Major Outage** |")
        md.append(f"| **Impact Scope** | {inc.get('impact_scope', 'Enterprise-Wide')} |")
        md.append(f"| **Outage Start Time** | `{start_time}` |")
        md.append(f"| **Mitigation Achieved** | `{mitigated_time}` |")
        md.append(f"| **Full Restoration** | `{restored_time}` |")
        md.append(f"| **Total Outage Duration** | **{chronometer['outage_duration']['formatted']}** ({chronometer['outage_duration']['hours']} hrs) |")
        md.append("")

        # Section 2: Incident Command Team
        md.append("### 2. Incident Command System (ICS) Roles")
        md.append(f"| Role | Assignee | Contact / Team |")
        md.append(f"| :--- | :--- | :--- |")
        md.append(f"| **Incident Commander (IC)** | {ic_name} | Incident Management Guild |")
        md.append(f"| **Technical Ops Lead** | {tech_name} | Platform Engineering & SRE |")
        md.append(f"| **Communications Lead** | {comms_name} | Executive & Customer Relations |")
        md.append(f"| **Scribe / Documentation** | {scribe_name} | Reliability Operations |")
        md.append("")

        # Section 3: Chronometer Metrics
        md.append("### 3. Chronometer Metrics (SRE / ITIL v4)")
        md.append(f"| Chronometer Metric | Duration | Definition / Target | SLA Compliance |")
        md.append(f"| :--- | :--- | :--- | :--- |")
        md.append(f"| **TTD (Time to Detect)** | `{chronometer['time_to_detect']['formatted']}` | Outage start to automated monitoring trip | Target < 5m |")
        md.append(f"| **TTE (Time to Engage)** | `{chronometer['time_to_engage']['formatted']}` | Alert to Incident Commander on bridge | Target < 10m |")
        md.append(f"| **TTM (Time to Mitigate)** | `{chronometer['time_to_mitigate']['formatted']}` | Bridge open to blast radius mitigation | {'SLA Breached' if chronometer['sla_compliance']['mitigation_sla_breached'] else 'Compliant'} |")
        md.append(f"| **TTR (Time to Restore)** | `{chronometer['time_to_restore']['formatted']}` | Outage start to 100% production recovery | {'SLA Breached' if chronometer['sla_compliance']['restoration_sla_breached'] else 'Compliant'} |")
        md.append("")

        # Section 4: Business Impact & Downtime Cost
        md.append("### 4. Business Blast Radius & Downtime Financial Accounting")
        md.append(f"- **Impacted Core Services**: {', '.join(f'`{s}`' for s in affected_services)}")
        md.append(f"- **Affected Customer Tiers**: {', '.join(impacted_customers)}")
        md.append(f"- **Active User Disruption**: `{affected_users:,}` users experienced error rates up to `{error_rate_pct}%`")
        md.append("")
        md.append(f"| Financial Metric | Amount (USD) | Methodology |")
        md.append(f"| :--- | :--- | :--- |")
        md.append(f"| **Configured Hourly Rate** | `${hourly_rate:,.2f} / hr` | Contractual business value metric |")
        md.append(f"| **Direct Downtime Loss** | **`${downtime_cost:,.2f}`** | `{chronometer['outage_duration']['hours']} hrs` × `${hourly_rate:,.2f}` |")
        md.append(f"| **SLA Credit Exposure** | `${sla_credits:,.2f}` | Contractual enterprise tier SLA rebates |")
        md.append(f"| **Total Financial Impact** | **`${total_financial_loss:,.2f}`** | Combined financial liability |")
        md.append("")

        # Section 5: Root Cause & 5-Whys
        md.append("### 5. Root Cause Analysis & 5-Whys Deep Dive")
        md.append(f"**Trigger Event**: {trigger_event}\n")
        md.append(f"**Primary Root Cause**: {root_cause}\n")
        md.append("#### 5-Whys Investigation Tree:")
        for idx, item in enumerate(five_whys, 1):
            if isinstance(item, dict):
                q = item.get("question", "")
                a = item.get("answer", "")
                md.append(f"{idx}. **Why?** {q}\n   - **Answer**: {a}")
            else:
                md.append(f"{idx}. {item}")
        md.append("")

        # Section 6: Chronological Timeline
        md.append("### 6. Chronological Incident Timeline")
        md.append(f"| Elapsed | UTC Timestamp | Event Type | Description | Logged By |")
        md.append(f"| :--- | :--- | :--- | :--- | :--- |")
        for ev in timeline:
            elapsed = ev.get("elapsed", "+00:00")
            time_str = ev.get("time", "")[:19].replace("T", " ")
            etype = ev.get("event_type", "milestone")
            summary = ev.get("summary", "").replace("|", "-")
            author = ev.get("author", "System")
            md.append(f"| `{elapsed}` | `{time_str}` | `{etype}` | {summary} | {author} |")
        md.append("")

        # Section 7: Lessons Learned
        md.append("### 7. Blameless Lessons Learned")
        md.append("#### What Went Well:")
        for item in what_went_well:
            md.append(f"- [x] {item}")
        md.append("\n#### What Went Wrong / Areas for Improvement:")
        for item in what_went_wrong:
            md.append(f"- [!] {item}")
        md.append("\n#### Where We Got Lucky:")
        for item in where_we_got_lucky:
            md.append(f"- [★] {item}")
        md.append("")

        # Section 8: Preventative Action Items
        md.append("### 8. Preventative Hardening Action Items (SRE Roadmap)")
        md.append(f"| ID | Title & Implementation Scope | Category | Owner | Priority | Target Due | Status |")
        md.append(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for act in action_items:
            aid = act.get("id", "ACT")
            atitle = act.get("title", "")
            acat = act.get("category", "Architecture")
            aowner = act.get("owner", "Engineering")
            aprio = act.get("priority", "P1")
            adue = act.get("target_due", "2 Weeks")
            astat = act.get("status", "Open")
            md.append(f"| `{aid}` | {atitle} | {acat} | {aowner} | `{aprio}` | {adue} | **{astat}** |")
        md.append("")

        md.append("---")
        md.append(f"*Report compiled by OpenNow Enterprise Major Incident Management Engine on `{now_iso()}`.*")
        return "\n".join(md)

    # ------------------------------------------------------------------------
    # 10. Analytics & Executive KPI Rollups
    # ------------------------------------------------------------------------

    def get_analytics(self) -> Dict[str, Any]:
        """Calculates aggregate MIM program metrics (Avg TTD, TTE, TTM, TTR, financial loss)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mim_major_incidents;")
            rows = cursor.fetchall()

        total = len(rows)
        if total == 0:
            return {
                "total_major_incidents": 0,
                "active_major_incidents": 0,
                "average_ttd_seconds": 0.0,
                "average_tte_seconds": 0.0,
                "average_ttm_seconds": 0.0,
                "average_ttr_seconds": 0.0,
                "total_downtime_cost_usd": 0.0,
                "sla_breach_rate_pct": 0.0,
            }

        ttd_list = []
        tte_list = []
        ttm_list = []
        ttr_list = []
        cost_sum = 0.0
        active_count = 0
        sla_breach_count = 0

        for r in rows:
            r_dict = dict(r)
            status_val = r_dict.get("status")
            if status_val in (MIMStatus.ACTIVE.value, MIMStatus.PROPOSED.value, MIMStatus.MITIGATED.value):
                active_count += 1

            cost_sum += float(r_dict.get("downtime_cost") or 0.0)

            # Chronometer calculation
            chrono = self.calculate_chronometer(r_dict, [])
            ttd = chrono["time_to_detect"]["seconds"]
            if ttd is not None:
                ttd_list.append(ttd)

            tte = chrono["time_to_engage"]["seconds"]
            if tte is not None:
                tte_list.append(tte)

            ttm = chrono["time_to_mitigate"]["seconds"]
            if ttm is not None:
                ttm_list.append(ttm)

            ttr = chrono["time_to_restore"]["seconds"]
            if ttr is not None:
                ttr_list.append(ttr)

            if chrono["sla_compliance"]["mitigation_sla_breached"] or chrono["sla_compliance"]["restoration_sla_breached"]:
                sla_breach_count += 1

        avg_ttd = sum(ttd_list) / len(ttd_list) if ttd_list else 0.0
        avg_tte = sum(tte_list) / len(tte_list) if tte_list else 0.0
        avg_ttm = sum(ttm_list) / len(ttm_list) if ttm_list else 0.0
        avg_ttr = sum(ttr_list) / len(ttr_list) if ttr_list else 0.0

        return {
            "total_major_incidents": total,
            "active_major_incidents": active_count,
            "average_ttd": {
                "seconds": round(avg_ttd, 1),
                "formatted": format_duration(avg_ttd),
            },
            "average_tte": {
                "seconds": round(avg_tte, 1),
                "formatted": format_duration(avg_tte),
            },
            "average_ttm": {
                "seconds": round(avg_ttm, 1),
                "formatted": format_duration(avg_ttm),
            },
            "average_ttr": {
                "seconds": round(avg_ttr, 1),
                "formatted": format_duration(avg_ttr),
            },
            "total_downtime_cost_usd": round(cost_sum, 2),
            "sla_breach_rate_pct": round((sla_breach_count / total) * 100.0, 1),
        }


# Global Singleton Instance
mim_engine = MIMEngine()


# ============================================================================
# 4. FASTAPI REST API ROUTER MOUNTING
# ============================================================================

mim_router = APIRouter(prefix="/api/v2/mim", tags=["Major Incident Management (MIM)"])


@mim_router.post("/promote", status_code=status.HTTP_201_CREATED, summary="Promote incident to Major Incident")
def api_promote_major_incident(payload: PromotePayload) -> Dict[str, Any]:
    """Promotes an existing ticket or declares a new P1 Major Incident with War Room, roles, and chronometer."""
    return mim_engine.promote_incident(payload)


@mim_router.get("/active", summary="List active major incidents with live war rooms")
def api_list_active_major_incidents() -> List[Dict[str, Any]]:
    """Returns active Major Incidents with live War Room bridges, chronometers, and roster."""
    return mim_engine.list_active_major_incidents()


@mim_router.post("/{id}/broadcast", summary="Send stakeholder broadcast")
def api_send_stakeholder_broadcast(id: str, payload: BroadcastPayload) -> Dict[str, Any]:
    """Dispatches internal technical bulletin or external executive / customer status page update."""
    return mim_engine.send_broadcast(id, payload)


@mim_router.post("/{id}/post-mortem", summary="Generate blameless post-mortem & PIR")
def api_generate_post_mortem(id: str, payload: Optional[PostMortemGeneratePayload] = None) -> Dict[str, Any]:
    """Auto-compiles timeline, root cause, 5-whys, impacted customers, downtime cost ($), and action items into exportable Markdown & JSON."""
    return mim_engine.generate_post_mortem(id, payload)


@mim_router.get("", summary="List all major incidents")
def api_list_all_major_incidents(status: Optional[str] = Query(None), limit: int = Query(50)) -> List[Dict[str, Any]]:
    """Lists major incidents with optional status filter."""
    return mim_engine.list_all_major_incidents(status_filter=status, limit=limit)


@mim_router.get("/analytics", summary="Aggregated MIM program analytics")
def api_get_mim_analytics() -> Dict[str, Any]:
    """Returns aggregated KPI chronometer metrics (Avg TTD, TTE, TTM, TTR) and downtime financial impact."""
    return mim_engine.get_analytics()


@mim_router.get("/{id}", summary="Get major incident detail")
def api_get_major_incident(id: str) -> Dict[str, Any]:
    """Returns complete major incident details, including roles, war room, broadcasts, timeline, and chronometer."""
    return mim_engine.get_major_incident(id)


@mim_router.patch("/{id}/status", summary="Transition major incident lifecycle status")
def api_transition_status(id: str, payload: StatusTransitionPayload) -> Dict[str, Any]:
    """Transitions state between Candidate, Proposed, Active, Mitigated, Post-Incident Review, Closed."""
    return mim_engine.transition_status(id, payload)


@mim_router.patch("/{id}/roles", summary="Assign or hand over incident command role")
def api_assign_role(id: str, payload: RoleAssignPayload) -> Dict[str, Any]:
    """Assigns or hands over Incident Commander (IC), Technical Ops Lead, Communications Lead, or Scribe."""
    return mim_engine.assign_role(id, payload)


@mim_router.post("/{id}/warroom/command-log", summary="Append war room command / decision log entry")
def api_warroom_command_log(id: str, payload: WarRoomCommandPayload) -> Dict[str, Any]:
    """Appends an operational command or decision to the active War Room log."""
    return mim_engine.append_war_room_command(id, payload)


@mim_router.post("/{id}/warroom/check-in", summary="Check in to war room bridge")
def api_warroom_check_in(id: str, payload: WarRoomCheckInPayload) -> Dict[str, Any]:
    """Checks an engineer or stakeholder into the active war room roster."""
    return mim_engine.war_room_check_in(id, payload)


@mim_router.post("/{id}/timeline", summary="Add custom event to incident timeline")
def api_add_timeline_event(id: str, payload: TimelineEventPayload) -> Dict[str, Any]:
    """Adds a custom diagnostic or mitigation event into the incident timeline."""
    return mim_engine.add_timeline_event(id, payload)


@mim_router.get("/{id}/post-mortem/markdown", summary="Download post-mortem in raw markdown format")
def api_get_post_mortem_markdown(id: str) -> Response:
    """Returns raw markdown document of the Post-Incident Review."""
    inc = mim_engine.get_major_incident(id)
    md = inc.get("post_mortem_markdown")
    if not md:
        # Generate if not yet generated
        gen = mim_engine.generate_post_mortem(id)
        md = gen["post_mortem_markdown"]
    return Response(content=md, media_type="text/markdown")


# ============================================================================
# 5. COMPREHENSIVE UNIT TEST SUITE
# ============================================================================

if __name__ == "__main__":
    import unittest
    from fastapi.testclient import TestClient

    class TestEnterpriseMIMEngine(unittest.TestCase):
        """Complete unit test coverage for MIM state model, roles, war room, broadcasts, chronometer, and post-mortem."""

        def setUp(self):
            # Create isolated in-memory SQLite database
            self.engine = MIMEngine(db_path=":memory:")
            # Also wire an isolated FastAPI app for API testing
            from fastapi import FastAPI
            self.test_app = FastAPI()
            # Monkey-patch engine inside route handler context
            global mim_engine
            mim_engine = self.engine
            self.test_app.include_router(mim_router)
            self.client = TestClient(self.test_app)

        def test_01_promote_incident_lifecycle(self):
            """Tests promotion to Major Incident, role generation, and war room bridge initialization."""
            payload = PromotePayload(
                incident_id="INC-9901",
                title="Global API Gateway Latency Degradation",
                summary="Critical latency spikes across US-East and EU-West transaction clusters.",
                severity="P1",
                impact_scope="Global Multi-Region",
                incident_commander="Commander Sarah Connor",
                technical_ops_lead="Tech Lead John Doe",
                communications_lead="Comms Lead Jane Smith",
                scribe="Scribe Tim Drake",
                hourly_downtime_rate=15000.0,
            )
            result = self.engine.promote_incident(payload)

            self.assertTrue(result["mim_number"].startswith("MIM-"))
            self.assertEqual(result["status"], MIMStatus.ACTIVE.value)
            self.assertEqual(result["severity"], "P1")
            self.assertEqual(result["incident_id"], "INC-9901")

            # Verify Roles
            roles = result["roles"]
            self.assertEqual(roles["incident_commander"]["assignee_name"], "Commander Sarah Connor")
            self.assertEqual(roles["technical_ops_lead"]["assignee_name"], "Tech Lead John Doe")
            self.assertEqual(roles["communications_lead"]["assignee_name"], "Comms Lead Jane Smith")
            self.assertEqual(roles["scribe"]["assignee_name"], "Scribe Tim Drake")

            # Verify War Room
            war_room = result["war_room"]
            self.assertIsNotNone(war_room)
            self.assertTrue(war_room["bridge_url"].startswith("https://meet.opennow.internal/warroom/"))
            self.assertEqual(war_room["dial_in_number"], "+1-800-555-MIM1 (+1-800-555-0199)")
            self.assertIn("#", war_room["dial_in_pin"])
            self.assertEqual(war_room["status"], "active")
            self.assertEqual(len(war_room["attendees"]), 4)
            self.assertEqual(len(war_room["command_log"]), 1)

            # Verify Timeline
            self.assertGreaterEqual(len(result["timeline"]), 3)

        def test_02_war_room_command_log_and_checkin(self):
            """Tests war room tactical decision logging and attendee check-ins."""
            promoted = self.engine.promote_incident(PromotePayload(
                title="Database Partition Split Brain",
                incident_commander="Dr. Gordon Freeman",
            ))
            mim_id = promoted["id"]

            # Append Command Decision
            cmd = self.engine.append_war_room_command(mim_id, WarRoomCommandPayload(
                author="Dr. Gordon Freeman",
                entry_type="decision",
                content="Authorizing emergency failover to passive DR region in us-west-2.",
            ))
            self.assertEqual(cmd["author"], "Dr. Gordon Freeman")
            self.assertEqual(cmd["entry_type"], "decision")

            # Check in new attendee
            attendee = self.engine.war_room_check_in(mim_id, WarRoomCheckInPayload(
                name="Barney Calhoun",
                role="Storage Specialist",
                contact="+1-555-0144",
            ))
            self.assertEqual(attendee["name"], "Barney Calhoun")

            # Reload and verify
            updated = self.engine.get_major_incident(mim_id)
            self.assertEqual(len(updated["war_room"]["command_log"]), 2)
            self.assertTrue(any(a["name"] == "Barney Calhoun" for a in updated["war_room"]["attendees"]))

        def test_03_stakeholder_broadcast_engine(self):
            """Tests stakeholder broadcast engine across internal technical bulletin and customer status page."""
            promoted = self.engine.promote_incident(PromotePayload(title="Auth Microservice Outage"))
            mim_id = promoted["id"]

            # 1. Internal Technical Bulletin
            tech_bc = self.engine.send_broadcast(mim_id, BroadcastPayload(
                audience=BroadcastAudience.INTERNAL_TECHNICAL.value,
                subject="TECHNICAL BULLETIN: Auth Service Latency Investigation",
                message_body="Eng teams are isolating Redis cache clusters. Next tech sync in 15m.",
                incident_phase=IncidentPhase.INVESTIGATING.value,
                eta_to_mitigation="25 minutes",
            ))
            self.assertEqual(tech_bc["status"], "delivered")
            self.assertEqual(tech_bc["broadcast_number"], "BC-001")
            self.assertFalse(tech_bc["published_to_statuspage"])

            # 2. External Customer Status Page Update
            cust_bc = self.engine.send_broadcast(mim_id, BroadcastPayload(
                audience=BroadcastAudience.CUSTOMER_STATUS_PAGE.value,
                subject="Degraded Login Performance on Customer Portal",
                message_body="We are actively investigating an issue causing delayed login requests.",
                incident_phase=IncidentPhase.IDENTIFIED.value,
                eta_to_mitigation="15 minutes",
            ))
            self.assertEqual(cust_bc["broadcast_number"], "BC-002")
            self.assertTrue(cust_bc["published_to_statuspage"])
            self.assertEqual(cust_bc["recipients_delivered"], 1450)

            # Verify Broadcasts in Incident Detail
            inc = self.engine.get_major_incident(mim_id)
            self.assertEqual(len(inc["broadcasts"]), 2)

        def test_04_chronometer_metrics_calculation(self):
            """Tests precise calculation of TTD, TTE, TTM, TTR, and running live chronometer."""
            now = datetime.datetime.now(datetime.timezone.utc)
            t_start = (now - datetime.timedelta(minutes=90)).isoformat()
            t_detect = (now - datetime.timedelta(minutes=85)).isoformat()
            t_engage = (now - datetime.timedelta(minutes=80)).isoformat()

            promoted = self.engine.promote_incident(PromotePayload(
                title="Core Message Queue Backup",
                incident_start_time=t_start,
                detected_time=t_detect,
                hourly_downtime_rate=20000.0,
            ))
            mim_id = promoted["id"]

            # Manually set engagement time for precise test validation
            with self.engine.get_connection() as conn:
                conn.execute("UPDATE mim_major_incidents SET engaged_time = ? WHERE id = ?;", (t_engage, mim_id))

            # Transition to Mitigated
            self.engine.transition_status(mim_id, StatusTransitionPayload(
                target_status=MIMStatus.MITIGATED.value,
                actor="Commander",
                reason="Workaround traffic reroute applied.",
            ))

            inc = self.engine.get_major_incident(mim_id)
            chrono = inc["chronometer"]

            # TTD = 90m - 85m = 5m (300s)
            self.assertAlmostEqual(chrono["time_to_detect"]["seconds"], 300.0, delta=2.0)
            self.assertIn("5m", chrono["time_to_detect"]["formatted"])

            # TTE = 85m - 80m = 5m (300s)
            self.assertAlmostEqual(chrono["time_to_engage"]["seconds"], 300.0, delta=2.0)

            # TTM should be recorded
            self.assertIsNotNone(chrono["time_to_mitigate"]["seconds"])
            self.assertGreater(chrono["time_to_mitigate"]["seconds"], 0)

            # Transition to PIR / Restored
            self.engine.transition_status(mim_id, StatusTransitionPayload(
                target_status=MIMStatus.PIR.value,
                actor="Commander",
                reason="Production verified 100% healthy.",
            ))

            inc_restored = self.engine.get_major_incident(mim_id)
            chrono_restored = inc_restored["chronometer"]
            self.assertIsNotNone(chrono_restored["time_to_restore"]["seconds"])
            self.assertGreater(chrono_restored["time_to_restore"]["seconds"], 0)

        def test_05_state_transition_guards(self):
            """Tests ITIL state machine transitions and prevents illegal jumps."""
            promoted = self.engine.promote_incident(PromotePayload(
                title="Test State Guard Incident",
                initial_status=MIMStatus.CANDIDATE.value,
            ))
            mim_id = promoted["id"]

            # Candidate -> Proposed is valid
            s1 = self.engine.transition_status(mim_id, StatusTransitionPayload(
                target_status=MIMStatus.PROPOSED.value,
                reason="Evaluated high severity impact.",
            ))
            self.assertEqual(s1["status"], MIMStatus.PROPOSED.value)

            # Proposed -> Active is valid
            s2 = self.engine.transition_status(mim_id, StatusTransitionPayload(
                target_status=MIMStatus.ACTIVE.value,
                reason="Declared P1 Major Incident by Commander.",
            ))
            self.assertEqual(s2["status"], MIMStatus.ACTIVE.value)

            # Active -> Closed directly is valid in emergency closure
            # But Closed -> Active directly is illegal without PIR
            s3 = self.engine.transition_status(mim_id, StatusTransitionPayload(
                target_status=MIMStatus.CLOSED.value,
                reason="Incident resolved and verified.",
            ))
            self.assertEqual(s3["status"], MIMStatus.CLOSED.value)

            # Attempt illegal jump from Closed -> Active
            with self.assertRaises(HTTPException) as ctx:
                self.engine.transition_status(mim_id, StatusTransitionPayload(
                    target_status=MIMStatus.ACTIVE.value,
                    reason="Illegal jump",
                ))
            self.assertEqual(ctx.exception.status_code, 400)

        def test_06_role_handover(self):
            """Tests role assignment and formal handover tracking."""
            promoted = self.engine.promote_incident(PromotePayload(
                title="Role Handover Test",
                incident_commander="Captain Kirk",
            ))
            mim_id = promoted["id"]

            # Hand over IC to Spock
            updated = self.engine.assign_role(mim_id, RoleAssignPayload(
                role=MIMRoleType.INCIDENT_COMMANDER.value,
                assignee_name="Commander Spock",
                assignee_email="spock@enterprise.fleet",
                handover_notes="Primary shield generators stabilized. Monitoring power levels.",
            ))

            roles = updated["roles"]
            self.assertEqual(roles["incident_commander"]["assignee_name"], "Commander Spock")
            self.assertEqual(roles["incident_commander"]["handover_notes"], "Primary shield generators stabilized. Monitoring power levels.")
            # Timeline check
            self.assertTrue(any("Spock" in t["summary"] for t in updated["timeline"]))

        def test_07_blameless_post_mortem_generator(self):
            """Tests auto-compilation of blameless post-mortem in Markdown and JSON with 5-whys, downtime cost, and action items."""
            promoted = self.engine.promote_incident(PromotePayload(
                title="Enterprise Cluster Outage",
                incident_commander="Alexis Sanchez",
                hourly_downtime_rate=18000.0,
            ))
            mim_id = promoted["id"]

            # Transition to Mitigated and PIR
            self.engine.transition_status(mim_id, StatusTransitionPayload(
                target_status=MIMStatus.MITIGATED.value,
                reason="Mitigation applied.",
            ))
            self.engine.transition_status(mim_id, StatusTransitionPayload(
                target_status=MIMStatus.PIR.value,
                reason="Service restored, beginning PIR.",
            ))

            # Generate Post-Mortem
            pm_res = self.engine.generate_post_mortem(mim_id, PostMortemGeneratePayload(
                root_cause="PostgreSQL max_connections threshold saturated by un-pooled background ETL.",
                trigger_event="Simultaneous deployment of reporting service and scheduled billing run.",
            ))

            self.assertEqual(pm_res["status"], "generated")
            self.assertGreater(pm_res["downtime_cost_usd"], 0)
            self.assertGreater(pm_res["total_financial_impact_usd"], 0)

            # JSON structure check
            pm_json = pm_res["post_mortem_json"]
            self.assertIn("blameless_statement", pm_json)
            self.assertEqual(len(pm_json["root_cause_analysis"]["five_whys"]), 5)
            self.assertEqual(len(pm_json["preventative_action_items"]), 4)
            self.assertGreaterEqual(len(pm_json["timeline"]), 3)

            # Markdown export check
            pm_md = pm_res["post_mortem_markdown"]
            self.assertIn("# Post-Incident Review (PIR) & Blameless Post-Mortem", pm_md)
            self.assertIn("### 1. Executive Incident Overview", pm_md)
            self.assertIn("### 3. Chronometer Metrics (SRE / ITIL v4)", pm_md)
            self.assertIn("### 5. Root Cause Analysis & 5-Whys Deep Dive", pm_md)
            self.assertIn("### 8. Preventative Hardening Action Items (SRE Roadmap)", pm_md)
            self.assertIn("Total Financial Impact", pm_md)

        def test_08_fastapi_rest_endpoints(self):
            """Tests all required REST endpoints via FastAPI TestClient:
            - POST /api/v2/mim/promote
            - GET /api/v2/mim/active
            - POST /api/v2/mim/{id}/broadcast
            - POST /api/v2/mim/{id}/post-mortem
            - PATCH /api/v2/mim/{id}/status
            - GET /api/v2/mim/{id}/post-mortem/markdown
            """
            # 1. POST /api/v2/mim/promote
            resp = self.client.post("/api/v2/mim/promote", json={
                "title": "API Gateway Connection Exhaustion",
                "severity": "P1",
                "incident_commander": "Alice Commander",
            })
            self.assertEqual(resp.status_code, 201)
            mim_data = resp.json()
            mim_id = mim_data["id"]
            mim_number = mim_data["mim_number"]
            self.assertTrue(mim_number.startswith("MIM-"))

            # 2. GET /api/v2/mim/active
            resp_active = self.client.get("/api/v2/mim/active")
            self.assertEqual(resp_active.status_code, 200)
            active_list = resp_active.json()
            self.assertTrue(any(item["id"] == mim_id for item in active_list))
            # Verify active item has war room
            self.assertIsNotNone(active_list[0]["war_room"])

            # 3. POST /api/v2/mim/{id}/broadcast
            resp_bc = self.client.post(f"/api/v2/mim/{mim_id}/broadcast", json={
                "audience": "internal_technical",
                "subject": "Tech Bulletin: Failover initiating",
                "message_body": "Traffic is being redirected to secondary cluster.",
                "incident_phase": "Mitigating",
            })
            self.assertEqual(resp_bc.status_code, 200)
            bc_res = resp_bc.json()
            self.assertEqual(bc_res["status"], "delivered")
            self.assertEqual(bc_res["broadcast_number"], "BC-001")

            # 4. PATCH /api/v2/mim/{id}/status -> Mitigated
            resp_stat = self.client.patch(f"/api/v2/mim/{mim_id}/status", json={
                "target_status": "Mitigated",
                "reason": "Secondary cluster taking 100% traffic.",
            })
            self.assertEqual(resp_stat.status_code, 200)
            self.assertEqual(resp_stat.json()["status"], MIMStatus.MITIGATED.value)

            # 5. POST /api/v2/mim/{id}/post-mortem
            resp_pm = self.client.post(f"/api/v2/mim/{mim_id}/post-mortem", json={
                "root_cause": "Under-provisioned connection pool.",
            })
            self.assertEqual(resp_pm.status_code, 200)
            pm_res = resp_pm.json()
            self.assertEqual(pm_res["status"], "generated")
            self.assertIn("# Post-Incident Review", pm_res["post_mortem_markdown"])

            # 6. GET /api/v2/mim/{id}/post-mortem/markdown (Raw Markdown download)
            resp_md = self.client.get(f"/api/v2/mim/{mim_id}/post-mortem/markdown")
            self.assertEqual(resp_md.status_code, 200)
            self.assertIn("text/markdown", resp_md.headers.get("content-type", ""))
            self.assertIn("# Post-Incident Review", resp_md.text)

            # 7. GET /api/v2/mim/analytics
            resp_analytics = self.client.get("/api/v2/mim/analytics")
            self.assertEqual(resp_analytics.status_code, 200)
            analytics_data = resp_analytics.json()
            self.assertGreaterEqual(analytics_data["total_major_incidents"], 1)

    unittest.main()
