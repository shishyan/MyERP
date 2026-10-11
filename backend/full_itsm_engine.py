"""OpenNow Full ITSM Engine & ITIL Suite
========================================
Reverse-engineered enterprise ITSM suite combining Zoho ServiceDesk Plus, GLPI, and iTop
architectural models for complete ITIL lifecycle operations.

Modules:
1. Problem Management & Known Error Database (KEDB)
2. Change Management & CAB Review
3. Release & Deployment Management
4. Service Catalog & Service Requests
5. Knowledge Management (KCS) & Incident Deflection
6. Asset & ITAM Contracts Management
7. Fast-API Router Mounting under /api/v2/
8. Unit Test Suite (under if __name__ == '__main__')
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sqlite3
import sys
import unittest
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

logger = logging.getLogger("opennow.full_itsm")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Default database directory and path
DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "opennow.db")


def now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 string format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ============================================================================
# PYDANTIC SCHEMAS FOR API & VALIDATION
# ============================================================================

# --- Problem Management Schemas ---
class ProblemCreate(BaseModel):
    title: str = Field(..., min_length=3, description="Problem title / summary")
    description: Optional[str] = Field("", description="Detailed problem statement and symptoms")
    category: Optional[str] = Field("Infrastructure", description="ITSM category")
    priority: Optional[str] = Field("P3", description="P1, P2, P3, P4")
    status: Optional[str] = Field("open", description="open, investigating, workaround_found, known_error, resolved, closed")
    root_cause: Optional[str] = Field("", description="Identified root cause")
    workaround: Optional[str] = Field("", description="Temporary operational workaround")
    permanent_solution: Optional[str] = Field("", description="Permanent architectural or code fix")
    five_whys: Optional[List[Union[str, Dict[str, Any]]]] = Field(default_factory=list, description="5-Whys root cause analysis")
    kedb_published: Optional[bool] = Field(False, description="Flag indicating if published to KEDB")


class ProblemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    root_cause: Optional[str] = None
    workaround: Optional[str] = None
    permanent_solution: Optional[str] = None
    five_whys: Optional[List[Union[str, Dict[str, Any]]]] = None
    kedb_published: Optional[bool] = None


class LinkIncidentsPayload(BaseModel):
    incident_ids: List[Union[str, int]] = Field(..., min_length=1, description="List of incident IDs or numbers to link")


class PublishKEDBPayload(BaseModel):
    kedb_published: bool = Field(True, description="Publish (true) or unpublish (false)")
    workaround: Optional[str] = Field(None, description="Optional updated workaround for KEDB")
    root_cause: Optional[str] = Field(None, description="Optional root cause summary")


class ProblemResolvePayload(BaseModel):
    permanent_solution: str = Field(..., min_length=3, description="Permanent solution description")
    root_cause: Optional[str] = Field("", description="Root cause summary")
    bulk_resolve_incidents: Optional[bool] = Field(True, description="Automatically resolve linked incidents")
    resolution_notes: Optional[str] = Field(None, description="Notes to copy into resolved incidents")


# --- Change Management Schemas ---
class ChangeCreate(BaseModel):
    title: str = Field(..., min_length=3, description="Change title / RFC summary")
    description: Optional[str] = Field("", description="Detailed description and scope of change")
    change_type: Optional[str] = Field("normal", description="standard, normal, emergency")
    risk_level: Optional[str] = Field("low", description="low, medium, high, critical")
    impact_summary: Optional[str] = Field("", description="Affected services and user base")
    backout_plan: Optional[str] = Field("", description="Rollback / recovery steps")
    test_plan: Optional[str] = Field("", description="Pre/post deployment validation tests")
    implementation_plan: Optional[str] = Field("", description="Step-by-step rollout schedule")
    scheduled_start: Optional[str] = Field(None, description="ISO timestamp for planned change start")
    scheduled_end: Optional[str] = Field(None, description="ISO timestamp for planned change end")


class ChangeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    change_type: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    impact_summary: Optional[str] = None
    backout_plan: Optional[str] = None
    test_plan: Optional[str] = None
    implementation_plan: Optional[str] = None
    cab_required: Optional[bool] = None
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None


class RiskAssessmentPayload(BaseModel):
    scope: str = Field("team", description="single_user, team, department, enterprise")
    downtime: str = Field("none", description="none, under_1h, 1h_to_4h, over_4h")
    reversibility: str = Field("trivial_rollback", description="trivial_rollback, moderate_rollback, complex_irreversible")
    testing: str = Field("automated_tested", description="automated_tested, manual_tested, partially_tested, untested")
    data_impact: str = Field("none", description="none, read_only, schema_migration, destructive")


class SubmitCABPayload(BaseModel):
    approvers: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Optional explicit approver list [{'name': '...', 'role': '...'}]"
    )
    comments: Optional[str] = Field("", description="Submission rationale or notes to CAB")


class CABVotePayload(BaseModel):
    approver_name: str = Field(..., min_length=2, description="Name or email of the voting CAB member")
    approver_role: Optional[str] = Field("CAB Member", description="Role of the voter (e.g. CAB Chair, Security Lead)")
    decision: str = Field(..., description="approved, rejected")
    comments: Optional[str] = Field("", description="Rationale or conditions of vote")


class ScheduleChangePayload(BaseModel):
    scheduled_start: str = Field(..., description="ISO 8601 start timestamp")
    scheduled_end: str = Field(..., description="ISO 8601 end timestamp")


class ChangeTransitionPayload(BaseModel):
    target_status: str = Field(..., description="implementing, review, closed, canceled")
    notes: Optional[str] = Field("", description="Transition notes or PIR summary")


# --- Release Management Schemas ---
class ReleaseCreate(BaseModel):
    title: str = Field(..., min_length=3, description="Release title")
    version: str = Field(..., min_length=1, description="Version tag, e.g. v2.5.0")
    release_type: Optional[str] = Field("minor", description="major, minor, patch, emergency")
    stage: Optional[str] = Field("planning", description="planning, development, testing, deployment, completed")
    release_notes: Optional[str] = Field("", description="Changelog and release notes")
    planned_date: Optional[str] = Field(None, description="ISO timestamp for planned release")


class ReleaseUpdate(BaseModel):
    title: Optional[str] = None
    version: Optional[str] = None
    release_type: Optional[str] = None
    stage: Optional[str] = None
    release_notes: Optional[str] = None
    planned_date: Optional[str] = None
    actual_date: Optional[str] = None


class ReleaseStagePayload(BaseModel):
    stage: str = Field(..., description="planning, development, testing, deployment, completed")
    notes: Optional[str] = Field("", description="Stage progression notes")


# --- Service Catalog Schemas ---
class CatalogItemCreate(BaseModel):
    name: str = Field(..., min_length=3, description="Service item name")
    category: str = Field(..., description="Item category (Hardware, Cloud, Access, Developer Tools)")
    description: Optional[str] = Field("", description="Item description and specifications")
    icon: Optional[str] = Field("package", description="Icon representation name")
    estimated_days: Optional[int] = Field(1, ge=0, description="Estimated turnaround business days")
    cost: Optional[float] = Field(0.0, ge=0.0, description="Internal chargeback cost")
    form_fields: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Custom form fields schema")
    is_active: Optional[bool] = Field(True, description="Whether item is orderable")


class CatalogItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    estimated_days: Optional[int] = None
    cost: Optional[float] = None
    form_fields: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None


class ServiceRequestCreate(BaseModel):
    catalog_item_id: int = Field(..., description="Target catalog item ID")
    requester_name: str = Field(..., min_length=2, description="Employee full name")
    requester_email: str = Field(..., min_length=3, description="Employee corporate email")
    form_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Values for the catalog item form")


class ServiceRequestStatusUpdate(BaseModel):
    status: str = Field(..., description="submitted, approval_pending, fulfilling, completed, rejected")
    comments: Optional[str] = Field("", description="Fulfillment comments or rejection reason")


# --- Knowledge Management Schemas ---
class KnowledgeArticleCreate(BaseModel):
    title: str = Field(..., min_length=3, description="Article title")
    content_html: str = Field(..., min_length=5, description="Article body in HTML or Markdown")
    category: Optional[str] = Field("General", description="Knowledge category")
    tags: Optional[str] = Field("", description="Comma-separated keyword tags")
    status: Optional[str] = Field("published", description="draft, published, retired")


class KnowledgeArticleUpdate(BaseModel):
    title: Optional[str] = None
    content_html: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None


# --- Asset & ITAM Contracts Schemas ---
class SoftwareLicenseCreate(BaseModel):
    software_name: str = Field(..., min_length=2, description="Software title")
    vendor: str = Field(..., min_length=2, description="Publisher or vendor")
    total_seats: int = Field(..., gt=0, description="Total licensed seats or count")
    allocated_seats: Optional[int] = Field(0, ge=0, description="Currently allocated seats")
    license_key: Optional[str] = Field("", description="License key or agreement number")
    expiry_date: Optional[str] = Field(None, description="ISO date of expiration")
    cost: Optional[float] = Field(0.0, ge=0.0, description="Annual license cost")


class SoftwareLicenseUpdate(BaseModel):
    software_name: Optional[str] = None
    vendor: Optional[str] = None
    total_seats: Optional[int] = None
    allocated_seats: Optional[int] = None
    license_key: Optional[str] = None
    expiry_date: Optional[str] = None
    cost: Optional[float] = None


class LicenseSeatAction(BaseModel):
    seats: int = Field(1, gt=0, description="Number of seats to allocate or release")
    user_or_host: Optional[str] = Field("", description="Identity of assigned user or host")


class VendorContractCreate(BaseModel):
    vendor_name: str = Field(..., min_length=2, description="Vendor / Provider legal name")
    contract_type: Optional[str] = Field("SaaS", description="SaaS, Hardware Support, Managed Services, Cloud Provider")
    start_date: str = Field(..., description="Contract start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Contract end date (YYYY-MM-DD)")
    annual_cost: Optional[float] = Field(0.0, ge=0.0, description="Annualized contract value")
    sla_terms: Optional[str] = Field("", description="Summary of SLA terms and support tiers")
    status: Optional[str] = Field("active", description="active, expired, under_negotiation, terminated")


class VendorContractUpdate(BaseModel):
    vendor_name: Optional[str] = None
    contract_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    annual_cost: Optional[float] = None
    sla_terms: Optional[str] = None
    status: Optional[str] = None


# ============================================================================
# CORE FULL ITSM DATABASE & BUSINESS LOGIC ENGINE
# ============================================================================

class FullITSMEngine:
    """Enterprise ITIL Engine managing Problems, Changes, Releases, Service Catalog,
    Knowledge Articles (KCS), and ITAM Contracts with SQLite WAL storage.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._shared_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:", timeout=30.0, check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
            self._shared_conn.execute("PRAGMA foreign_keys = ON;")
        self._ensure_db_dir()
        self.init_schema()
        self.seed_defaults()

    def _ensure_db_dir(self) -> None:
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Thread-safe SQLite connection manager with WAL and foreign key support."""
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

    def close(self) -> None:
        if self._shared_conn is not None:
            try:
                self._shared_conn.close()
            except Exception:
                pass
            self._shared_conn = None

    def init_schema(self) -> None:
        """Initializes all ITSM tables and relational constraints."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Problem Management & KEDB
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_problems (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    problem_number TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT 'Infrastructure',
                    priority TEXT DEFAULT 'P3',
                    status TEXT NOT NULL DEFAULT 'open',
                    root_cause TEXT DEFAULT '',
                    workaround TEXT DEFAULT '',
                    permanent_solution TEXT DEFAULT '',
                    five_whys_json TEXT DEFAULT '[]',
                    kedb_published INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT DEFAULT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_problem_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    problem_id INTEGER NOT NULL,
                    incident_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (problem_id) REFERENCES itsm_problems(id) ON DELETE CASCADE,
                    UNIQUE(problem_id, incident_id)
                );
            """)

            # 2. Change Management & CAB Review
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    change_number TEXT UNIQUE NOT NULL,
                    change_type TEXT NOT NULL DEFAULT 'normal',
                    status TEXT NOT NULL DEFAULT 'draft',
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    risk_level TEXT DEFAULT 'low',
                    risk_score INTEGER DEFAULT 0,
                    impact_summary TEXT DEFAULT '',
                    backout_plan TEXT DEFAULT '',
                    test_plan TEXT DEFAULT '',
                    implementation_plan TEXT DEFAULT '',
                    cab_required INTEGER DEFAULT 0,
                    scheduled_start TEXT DEFAULT NULL,
                    scheduled_end TEXT DEFAULT NULL,
                    questionnaire_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_change_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    change_id INTEGER NOT NULL,
                    approver_name TEXT NOT NULL,
                    approver_role TEXT NOT NULL,
                    decision TEXT NOT NULL DEFAULT 'pending',
                    comments TEXT DEFAULT '',
                    decided_at TEXT DEFAULT NULL,
                    FOREIGN KEY (change_id) REFERENCES itsm_changes(id) ON DELETE CASCADE,
                    UNIQUE(change_id, approver_name, approver_role)
                );
            """)

            # 3. Release & Deployment Management
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_releases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    release_number TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    release_type TEXT NOT NULL DEFAULT 'minor',
                    stage TEXT NOT NULL DEFAULT 'planning',
                    version TEXT NOT NULL,
                    release_notes TEXT DEFAULT '',
                    planned_date TEXT DEFAULT NULL,
                    actual_date TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            # 4. Service Catalog & Service Requests
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_catalog_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    icon TEXT DEFAULT 'package',
                    estimated_days INTEGER DEFAULT 1,
                    cost REAL DEFAULT 0.0,
                    form_fields_json TEXT DEFAULT '[]',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_service_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_number TEXT UNIQUE NOT NULL,
                    catalog_item_id INTEGER NOT NULL,
                    requester_name TEXT NOT NULL,
                    requester_email TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'submitted',
                    form_data_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT NULL,
                    FOREIGN KEY (catalog_item_id) REFERENCES itsm_catalog_items(id)
                );
            """)

            # 5. Knowledge Management (KCS)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_knowledge_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_number TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    content_html TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'General',
                    tags TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    view_count INTEGER DEFAULT 0,
                    helpful_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 6. Asset & ITAM Contracts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_software_licenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    software_name TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    total_seats INTEGER NOT NULL DEFAULT 1,
                    allocated_seats INTEGER NOT NULL DEFAULT 0,
                    license_key TEXT DEFAULT '',
                    expiry_date TEXT DEFAULT NULL,
                    cost REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itsm_vendor_contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_name TEXT NOT NULL,
                    contract_type TEXT NOT NULL DEFAULT 'SaaS',
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    annual_cost REAL DEFAULT 0.0,
                    sla_terms TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL
                );
            """)

            # Optional indexes for high query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_problems_status ON itsm_problems(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_changes_status ON itsm_changes(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_releases_stage ON itsm_releases(stage);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON itsm_service_requests(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kb_status ON itsm_knowledge_articles(status);")

    def seed_defaults(self) -> None:
        """Seeds mandatory catalog items, sample licenses, contracts, and knowledge base articles."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Seed Service Catalog Items
            catalog_items = [
                (
                    "Developer Laptop Provisioning",
                    "Hardware & Devices",
                    "Request standard high-performance Apple M3 Pro or Dell Precision developer workstation with peripheral kit.",
                    "laptop",
                    3,
                    2499.00,
                    json.dumps([
                        {"name": "os_preference", "label": "Operating System", "type": "select", "options": ["macOS (M3 Pro 36GB)", "Ubuntu Linux (64GB)", "Windows 11 Pro (64GB)"], "required": True},
                        {"name": "shipping_address", "label": "Direct Shipping Address", "type": "textarea", "required": True},
                        {"name": "monitor_dock_required", "label": "Include 4K Monitor & Thunderbolt Dock", "type": "boolean", "default": True}
                    ]),
                    1,
                    now_iso()
                ),
                (
                    "AWS Sandbox Access",
                    "Cloud & Infrastructure",
                    "Temporary isolated AWS sandbox account provisioned with $500 monthly spend limit and SSO authentication.",
                    "cloud",
                    1,
                    500.00,
                    json.dumps([
                        {"name": "project_name", "label": "Project / Experiment Title", "type": "text", "required": True},
                        {"name": "duration_months", "label": "Duration (Months)", "type": "number", "default": 3, "required": True},
                        {"name": "region_preference", "label": "Primary AWS Region", "type": "select", "options": ["us-east-1", "eu-west-1", "ap-southeast-1"], "required": True}
                    ]),
                    1,
                    now_iso()
                ),
                (
                    "VPN & Teleport Remote Access",
                    "Security & Network",
                    "WireGuard Global VPN profile and Teleport SSH/Kubernetes cluster access credentials.",
                    "shield",
                    1,
                    0.00,
                    json.dumps([
                        {"name": "cluster_environment", "label": "Target Environment", "type": "select", "options": ["Staging", "Production-Read-Only", "Dev-Infra"], "required": True},
                        {"name": "business_justification", "label": "Business Justification", "type": "textarea", "required": True}
                    ]),
                    1,
                    now_iso()
                ),
                (
                    "JetBrains All Products License",
                    "Developer Tools",
                    "Annual floating enterprise license for IntelliJ IDEA Ultimate, PyCharm, WebStorm, and CLion.",
                    "code",
                    1,
                    289.00,
                    json.dumps([
                        {"name": "github_username", "label": "Corporate GitHub Username", "type": "text", "required": True},
                        {"name": "primary_ide", "label": "Primary IDE Needed", "type": "select", "options": ["IntelliJ IDEA Ultimate", "PyCharm Professional", "WebStorm", "GoLand"], "required": True}
                    ]),
                    1,
                    now_iso()
                ),
            ]

            for item in catalog_items:
                cursor.execute("""
                    INSERT OR IGNORE INTO itsm_catalog_items
                    (name, category, description, icon, estimated_days, cost, form_fields_json, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, item)

            # 2. Seed Software Licenses
            licenses = [
                ("JetBrains All Products Pack", "JetBrains s.r.o.", 100, 82, "JB-CORP-9482-ENT", "2027-12-31", 28900.00, now_iso()),
                ("Microsoft 365 E5 Suite", "Microsoft Corporation", 500, 460, "MSFT-E5-ENTERPRISE-TENANT", "2027-06-30", 216000.00, now_iso()),
                ("Slack Enterprise Grid", "Salesforce Inc.", 600, 520, "SLACK-GRID-ENT-CORP", "2027-09-15", 72000.00, now_iso()),
                ("GitHub Enterprise Cloud", "GitHub / Microsoft", 250, 210, "GH-ENT-SEATS-250", "2027-11-01", 52500.00, now_iso()),
            ]
            for lic in licenses:
                cursor.execute("""
                    INSERT OR IGNORE INTO itsm_software_licenses
                    (software_name, vendor, total_seats, allocated_seats, license_key, expiry_date, cost, created_at)
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (SELECT 1 FROM itsm_software_licenses WHERE software_name = ?);
                """, (*lic, lic[0]))

            # 3. Seed Vendor Contracts
            contracts = [
                ("Amazon Web Services", "Cloud Provider", "2025-01-01", "2027-12-31", 180000.00, "15-minute P1 incident response, 24x7 Enterprise Support, Dedicated TAM", "active", now_iso()),
                ("Okta Identity Cloud", "SaaS", "2025-03-01", "2026-03-01", 95000.00, "99.99% service SLA, 1-hour P1 escalation guarantee", "active", now_iso()),
                ("Cisco Systems Data Center", "Hardware Support", "2024-06-01", "2026-06-01", 45000.00, "SmartNet 24x7x4hr on-site hardware replacement SLA", "active", now_iso()),
            ]
            for contract in contracts:
                cursor.execute("""
                    INSERT OR IGNORE INTO itsm_vendor_contracts
                    (vendor_name, contract_type, start_date, end_date, annual_cost, sla_terms, status, created_at)
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (SELECT 1 FROM itsm_vendor_contracts WHERE vendor_name = ?);
                """, (*contract, contract[0]))

            # 4. Seed Knowledge Articles (KCS)
            articles = [
                (
                    "KB00001",
                    "Self-Service Password Reset & MFA Recovery Protocol",
                    "<p>To reset your corporate Okta password or re-enroll Microsoft Authenticator, navigate to <code>https://auth.company.corp/recovery</code>. Ensure your registered mobile SMS or hardware FIDO2 key is handy. If locked out, contact the automated voice hotline at ext 4357.</p>",
                    "Access & Identity",
                    "password, mfa, okta, reset, authentication, login, locked",
                    "published",
                    142,
                    38,
                    now_iso(),
                    now_iso()
                ),
                (
                    "KB00002",
                    "Global WireGuard VPN Setup & DNS Troubleshooting",
                    "<p>Install WireGuard client from the IT self-service portal. Import profile <code>wg-corp-global.conf</code>. In case of DNS resolution failures, run <code>sudo systemd-resolve --flush-caches</code> or verify 10.0.0.2 is in <code>/etc/resolv.conf</code>.</p>",
                    "Network & VPN",
                    "vpn, wireguard, network, dns, remote access, connection",
                    "published",
                    95,
                    27,
                    now_iso(),
                    now_iso()
                ),
                (
                    "KB00003",
                    "Developer MacBook Onboarding & Teleport SSH Access",
                    "<p>Use Teleport CLI (<code>tsh login --proxy=teleport.company.corp</code>) with corporate SSO. Once authenticated, run <code>tsh ssh root@target-host</code> or configure <code>~/.tsh/config</code> for transparent SSH integration.</p>",
                    "Developer Infrastructure",
                    "teleport, ssh, developer, macbook, kubernetes, access",
                    "published",
                    210,
                    64,
                    now_iso(),
                    now_iso()
                ),
                (
                    "KB00004",
                    "PostgreSQL Connection Pool Exhaustion & Deadlock Runbook",
                    "<p>When receiving 'remaining connection slots are reserved for non-replication superuser connections', check PgBouncer pool limits with <code>SHOW POOLS;</code>. Terminate idle-in-transaction connections using <code>SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND state_change < now() - interval '5 minutes';</code>.</p>",
                    "Database",
                    "database, postgres, pgbouncer, pool, deadlock, timeout, connections",
                    "published",
                    78,
                    19,
                    now_iso(),
                    now_iso()
                ),
            ]
            for art in articles:
                cursor.execute("""
                    INSERT OR IGNORE INTO itsm_knowledge_articles
                    (article_number, title, content_html, category, tags, status, view_count, helpful_count, created_at, updated_at)
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (SELECT 1 FROM itsm_knowledge_articles WHERE article_number = ?);
                """, (*art, art[0]))

    # -------------------------------------------------------------------------
    # UTILITY: IDENTIFIER GENERATORS
    # -------------------------------------------------------------------------
    def _next_number(self, table_name: str, prefix: str) -> str:
        """Generates sequential standard ITSM numbers (PRB00001, CHG00001, etc.)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}")
            row = cursor.fetchone()
            count = (row["cnt"] if row else 0) + 1
            # Ensure uniqueness loop
            while True:
                candidate = f"{prefix}{count:05d}"
                col = "problem_number" if "problem" in table_name else (
                    "change_number" if "change" in table_name else (
                        "release_number" if "release" in table_name else (
                            "request_number" if "request" in table_name else "article_number"
                        )
                    )
                )
                cursor.execute(f"SELECT 1 FROM {table_name} WHERE {col} = ?", (candidate,))
                if not cursor.fetchone():
                    return candidate
                count += 1

    # =========================================================================
    # 1. PROBLEM MANAGEMENT & KEDB
    # =========================================================================

    def create_problem(self, payload: ProblemCreate) -> Dict[str, Any]:
        prob_num = self._next_number("itsm_problems", "PRB")
        created = now_iso()
        five_whys_str = json.dumps(payload.five_whys or [])
        kedb_flag = 1 if payload.kedb_published else 0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO itsm_problems
                (problem_number, title, description, category, priority, status,
                 root_cause, workaround, permanent_solution, five_whys_json, kedb_published, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prob_num, payload.title, payload.description or "", payload.category or "Infrastructure",
                payload.priority or "P3", payload.status or "open", payload.root_cause or "",
                payload.workaround or "", payload.permanent_solution or "", five_whys_str, kedb_flag, created
            ))
            problem_id = cursor.lastrowid

        return self.get_problem(problem_id)

    def get_problem(self, problem_id_or_number: Union[int, str]) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(problem_id_or_number, int) or (isinstance(problem_id_or_number, str) and problem_id_or_number.isdigit()):
                cursor.execute("SELECT * FROM itsm_problems WHERE id = ?", (int(problem_id_or_number),))
            else:
                cursor.execute("SELECT * FROM itsm_problems WHERE problem_number = ?", (str(problem_id_or_number),))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Problem {problem_id_or_number} not found.")

            prob = dict(row)
            try:
                prob["five_whys"] = json.loads(prob.get("five_whys_json") or "[]")
            except Exception:
                prob["five_whys"] = []
            prob["kedb_published"] = bool(prob.get("kedb_published"))

            # Fetch linked incidents
            cursor.execute("SELECT incident_id, created_at FROM itsm_problem_incidents WHERE problem_id = ?", (prob["id"],))
            prob["linked_incidents"] = [dict(r) for r in cursor.fetchall()]
            return prob

    def list_problems(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        kedb_published: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if priority:
            clauses.append("priority = ?")
            params.append(priority)
        if kedb_published is not None:
            clauses.append("kedb_published = ?")
            params.append(1 if kedb_published else 0)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM itsm_problems {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                p = dict(r)
                try:
                    p["five_whys"] = json.loads(p.get("five_whys_json") or "[]")
                except Exception:
                    p["five_whys"] = []
                p["kedb_published"] = bool(p.get("kedb_published"))
                # Get linked count
                cursor.execute("SELECT COUNT(*) AS cnt FROM itsm_problem_incidents WHERE problem_id = ?", (p["id"],))
                cnt_row = cursor.fetchone()
                p["linked_incident_count"] = cnt_row["cnt"] if cnt_row else 0
                results.append(p)
            return results

    def update_problem(self, problem_id: int, payload: ProblemUpdate) -> Dict[str, Any]:
        existing = self.get_problem(problem_id)
        updates = []
        params = []

        fields = {
            "title": payload.title,
            "description": payload.description,
            "category": payload.category,
            "priority": payload.priority,
            "status": payload.status,
            "root_cause": payload.root_cause,
            "workaround": payload.workaround,
            "permanent_solution": payload.permanent_solution,
        }
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = ?")
                params.append(v)

        if payload.five_whys is not None:
            updates.append("five_whys_json = ?")
            params.append(json.dumps(payload.five_whys))

        if payload.kedb_published is not None:
            updates.append("kedb_published = ?")
            params.append(1 if payload.kedb_published else 0)

        if updates:
            params.append(problem_id)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE itsm_problems SET {', '.join(updates)} WHERE id = ?", params)

        return self.get_problem(problem_id)

    def delete_problem(self, problem_id: int) -> bool:
        self.get_problem(problem_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM itsm_problem_incidents WHERE problem_id = ?", (problem_id,))
            cursor.execute("DELETE FROM itsm_problems WHERE id = ?", (problem_id,))
            return cursor.rowcount > 0

    def link_incidents(self, problem_id: int, incident_ids: List[Union[str, int]]) -> Dict[str, Any]:
        self.get_problem(problem_id)
        created = now_iso()
        linked_count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for inc in incident_ids:
                inc_str = str(inc).strip()
                if not inc_str:
                    continue
                cursor.execute("""
                    INSERT OR IGNORE INTO itsm_problem_incidents (problem_id, incident_id, created_at)
                    VALUES (?, ?, ?)
                """, (problem_id, inc_str, created))
                if cursor.rowcount > 0:
                    linked_count += 1
        return {
            "success": True,
            "problem_id": problem_id,
            "linked_new_incidents": linked_count,
            "problem": self.get_problem(problem_id)
        }

    def unlink_incident(self, problem_id: int, incident_id: Union[str, int]) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM itsm_problem_incidents WHERE problem_id = ? AND incident_id = ?", (problem_id, str(incident_id)))
            return {"success": True, "removed": cursor.rowcount > 0}

    def publish_to_kedb(self, problem_id: int, payload: PublishKEDBPayload) -> Dict[str, Any]:
        prob = self.get_problem(problem_id)
        updates = ["kedb_published = ?"]
        params = [1 if payload.kedb_published else 0]

        if payload.workaround is not None:
            updates.append("workaround = ?")
            params.append(payload.workaround)
        if payload.root_cause is not None:
            updates.append("root_cause = ?")
            params.append(payload.root_cause)

        # If publishing and status is still open or investigating, update status to known_error
        if payload.kedb_published and prob["status"] in ("open", "investigating", "workaround_found"):
            updates.append("status = ?")
            params.append("known_error")

        params.append(problem_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE itsm_problems SET {', '.join(updates)} WHERE id = ?", params)

        return self.get_problem(problem_id)

    def resolve_problem(self, problem_id: int, payload: ProblemResolvePayload) -> Dict[str, Any]:
        prob = self.get_problem(problem_id)
        resolved_ts = now_iso()
        res_notes = payload.resolution_notes or f"Problem {prob['problem_number']} resolved: {payload.permanent_solution}"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE itsm_problems
                SET status = 'resolved',
                    permanent_solution = ?,
                    root_cause = CASE WHEN ? != '' THEN ? ELSE root_cause END,
                    resolved_at = ?
                WHERE id = ?
            """, (payload.permanent_solution, payload.root_cause or "", payload.root_cause or "", resolved_ts, problem_id))

            bulk_resolved = []
            if payload.bulk_resolve_incidents:
                cursor.execute("SELECT incident_id FROM itsm_problem_incidents WHERE problem_id = ?", (problem_id,))
                rows = cursor.fetchall()
                for r in rows:
                    inc_id = r["incident_id"]
                    # 1. Update in v2_incidents if table exists
                    try:
                        cursor.execute("""
                            UPDATE v2_incidents
                            SET state = 'Resolved',
                                resolution_code = 'Problem Resolved (Permanent Fix)',
                                resolution_notes = ?,
                                root_cause = ?,
                                resolved_at = ?
                            WHERE incident_number = ? OR id = ?
                        """, (res_notes, payload.root_cause or prob.get("root_cause", ""), resolved_ts, inc_id, inc_id))
                    except Exception:
                        pass

                    # 2. Update in tasks if table exists
                    try:
                        cursor.execute("""
                            UPDATE tasks
                            SET status = 'resolved',
                                updated_at = ?
                            WHERE task_number = ? OR id = ?
                        """, (resolved_ts, inc_id, inc_id))
                    except Exception:
                        pass
                    bulk_resolved.append(inc_id)

        return {
            "success": True,
            "problem": self.get_problem(problem_id),
            "bulk_resolved_incidents": bulk_resolved,
            "count_resolved": len(bulk_resolved)
        }

    def search_kedb(self, query: str = "", category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches Known Error Database published entries."""
        tokens = [t.lower() for t in re.findall(r"\w+", query)] if query else []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql = "SELECT * FROM itsm_problems WHERE kedb_published = 1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " ORDER BY id DESC"
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            results = []
            for r in rows:
                p = dict(r)
                p["kedb_published"] = True
                try:
                    p["five_whys"] = json.loads(p.get("five_whys_json") or "[]")
                except Exception:
                    p["five_whys"] = []

                if tokens:
                    searchable = f"{p['problem_number']} {p['title']} {p['description']} {p['root_cause']} {p['workaround']} {p['permanent_solution']}".lower()
                    if not any(token in searchable for token in tokens):
                        continue
                results.append(p)
            return results

    # =========================================================================
    # 2. CHANGE MANAGEMENT & CAB REVIEW
    # =========================================================================

    def calculate_risk(self, questionnaire: RiskAssessmentPayload) -> Tuple[int, str, bool]:
        """Calculates risk score (0-27), risk level, and whether CAB review is required."""
        scope_weights = {"single_user": 1, "team": 2, "department": 3, "enterprise": 5}
        downtime_weights = {"none": 0, "under_1h": 2, "1h_to_4h": 4, "over_4h": 6}
        reversibility_weights = {"trivial_rollback": 1, "moderate_rollback": 3, "complex_irreversible": 5}
        testing_weights = {"automated_tested": 1, "manual_tested": 2, "partially_tested": 4, "untested": 6}
        data_weights = {"none": 0, "read_only": 1, "schema_migration": 3, "destructive": 5}

        score = (
            scope_weights.get(questionnaire.scope, 2) +
            downtime_weights.get(questionnaire.downtime, 0) +
            reversibility_weights.get(questionnaire.reversibility, 2) +
            testing_weights.get(questionnaire.testing, 2) +
            data_weights.get(questionnaire.data_impact, 0)
        )

        if score <= 6:
            risk_level = "low"
            cab_required = False
        elif score <= 12:
            risk_level = "medium"
            cab_required = False
        elif score <= 18:
            risk_level = "high"
            cab_required = True
        else:
            risk_level = "critical"
            cab_required = True

        return score, risk_level, cab_required

    def create_change(self, payload: ChangeCreate) -> Dict[str, Any]:
        chg_num = self._next_number("itsm_changes", "CHG")
        created = now_iso()

        # Initial risk assessment defaults
        risk_score = 4 if payload.risk_level == "low" else (8 if payload.risk_level == "medium" else (14 if payload.risk_level == "high" else 20))
        cab_required = 1 if (payload.change_type in ("emergency", "normal") and payload.risk_level in ("high", "critical")) else 0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO itsm_changes
                (change_number, change_type, status, title, description, risk_level,
                 risk_score, impact_summary, backout_plan, test_plan, implementation_plan,
                 cab_required, scheduled_start, scheduled_end, created_at)
                VALUES (?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chg_num, payload.change_type or "normal", payload.title, payload.description or "",
                payload.risk_level or "low", risk_score, payload.impact_summary or "",
                payload.backout_plan or "", payload.test_plan or "", payload.implementation_plan or "",
                cab_required, payload.scheduled_start, payload.scheduled_end, created
            ))
            change_id = cursor.lastrowid

        return self.get_change(change_id)

    def get_change(self, change_id_or_number: Union[int, str]) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(change_id_or_number, int) or (isinstance(change_id_or_number, str) and change_id_or_number.isdigit()):
                cursor.execute("SELECT * FROM itsm_changes WHERE id = ?", (int(change_id_or_number),))
            else:
                cursor.execute("SELECT * FROM itsm_changes WHERE change_number = ?", (str(change_id_or_number),))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Change {change_id_or_number} not found.")

            chg = dict(row)
            chg["cab_required"] = bool(chg.get("cab_required"))
            try:
                chg["questionnaire"] = json.loads(chg.get("questionnaire_json") or "{}")
            except Exception:
                chg["questionnaire"] = {}

            # Fetch Approvals
            cursor.execute("SELECT * FROM itsm_change_approvals WHERE change_id = ? ORDER BY id ASC", (chg["id"],))
            chg["approvals"] = [dict(r) for r in cursor.fetchall()]
            return chg

    def list_changes(
        self,
        change_type: Optional[str] = None,
        status: Optional[str] = None,
        risk_level: Optional[str] = None,
        cab_required: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if change_type:
            clauses.append("change_type = ?")
            params.append(change_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if risk_level:
            clauses.append("risk_level = ?")
            params.append(risk_level)
        if cab_required is not None:
            clauses.append("cab_required = ?")
            params.append(1 if cab_required else 0)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM itsm_changes {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                c = dict(r)
                c["cab_required"] = bool(c.get("cab_required"))
                results.append(c)
            return results

    def update_change(self, change_id: int, payload: ChangeUpdate) -> Dict[str, Any]:
        self.get_change(change_id)
        updates = []
        params = []

        fields = {
            "title": payload.title,
            "description": payload.description,
            "change_type": payload.change_type,
            "status": payload.status,
            "risk_level": payload.risk_level,
            "risk_score": payload.risk_score,
            "impact_summary": payload.impact_summary,
            "backout_plan": payload.backout_plan,
            "test_plan": payload.test_plan,
            "implementation_plan": payload.implementation_plan,
            "scheduled_start": payload.scheduled_start,
            "scheduled_end": payload.scheduled_end,
        }
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = ?")
                params.append(v)

        if payload.cab_required is not None:
            updates.append("cab_required = ?")
            params.append(1 if payload.cab_required else 0)

        if updates:
            params.append(change_id)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE itsm_changes SET {', '.join(updates)} WHERE id = ?", params)

        return self.get_change(change_id)

    def delete_change(self, change_id: int) -> bool:
        self.get_change(change_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM itsm_change_approvals WHERE change_id = ?", (change_id,))
            cursor.execute("DELETE FROM itsm_changes WHERE id = ?", (change_id,))
            return cursor.rowcount > 0

    def assess_risk(self, change_id: int, questionnaire: RiskAssessmentPayload) -> Dict[str, Any]:
        """Calculates risk score, determines risk level & CAB requirement, and updates change record."""
        chg = self.get_change(change_id)
        score, risk_level, cab_req = self.calculate_risk(questionnaire)

        # Force CAB required if emergency
        if chg["change_type"] == "emergency":
            cab_req = True

        with self.get_connection() as conn:
            questionnaire_data = questionnaire.model_dump() if hasattr(questionnaire, "model_dump") else questionnaire.dict()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE itsm_changes
                SET risk_score = ?,
                    risk_level = ?,
                    cab_required = ?,
                    questionnaire_json = ?
                WHERE id = ?
            """, (score, risk_level, 1 if cab_req else 0, json.dumps(questionnaire_data), change_id))

        return self.get_change(change_id)

    def submit_to_cab(self, change_id: int, payload: SubmitCABPayload) -> Dict[str, Any]:
        """Validates change plans and submits change to CAB review with default or custom reviewers."""
        chg = self.get_change(change_id)

        # Validation: for Normal or Emergency, plans are recommended
        missing_plans = []
        if not chg.get("implementation_plan"):
            missing_plans.append("implementation_plan")
        if not chg.get("backout_plan"):
            missing_plans.append("backout_plan")

        approvers = payload.approvers or [
            {"name": "Enterprise CAB Chair", "role": "CAB Chair"},
            {"name": "Chief Information Security Officer", "role": "Security Lead"},
            {"name": "Infrastructure Operations Director", "role": "Infra Lead"},
        ]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE itsm_changes
                SET status = 'cab_review',
                    cab_required = 1
                WHERE id = ?
            """, (change_id,))

            # Insert approvers if not already created
            for appr in approvers:
                cursor.execute("""
                    INSERT OR IGNORE INTO itsm_change_approvals
                    (change_id, approver_name, approver_role, decision, comments)
                    VALUES (?, ?, ?, 'pending', '')
                """, (change_id, appr["name"], appr["role"]))

        return {
            "success": True,
            "warning": f"Plans missing: {', '.join(missing_plans)}" if missing_plans else None,
            "change": self.get_change(change_id)
        }

    def cast_cab_vote(self, change_id: int, payload: CABVotePayload) -> Dict[str, Any]:
        """Casts vote on behalf of a CAB approver and checks if all approvers have decided."""
        chg = self.get_change(change_id)
        decided_at = now_iso()
        norm_decision = payload.decision.lower().strip()
        if norm_decision not in ("approved", "rejected"):
            raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check if approver row exists
            cursor.execute("""
                SELECT id FROM itsm_change_approvals
                WHERE change_id = ? AND (approver_name = ? OR approver_role = ?)
            """, (change_id, payload.approver_name, payload.approver_role or payload.approver_name))
            row = cursor.fetchone()

            if row:
                cursor.execute("""
                    UPDATE itsm_change_approvals
                    SET decision = ?, comments = ?, decided_at = ?
                    WHERE id = ?
                """, (norm_decision, payload.comments or "", decided_at, row["id"]))
            else:
                cursor.execute("""
                    INSERT INTO itsm_change_approvals
                    (change_id, approver_name, approver_role, decision, comments, decided_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (change_id, payload.approver_name, payload.approver_role or "CAB Member", norm_decision, payload.comments or "", decided_at))

        updated_chg = self.get_change(change_id)
        all_approved = all(a["decision"] == "approved" for a in updated_chg["approvals"]) and len(updated_chg["approvals"]) > 0
        any_rejected = any(a["decision"] == "rejected" for a in updated_chg["approvals"])

        return {
            "success": True,
            "vote_recorded": norm_decision,
            "all_approved": all_approved,
            "any_rejected": any_rejected,
            "change": updated_chg
        }

    def schedule_change(self, change_id: int, payload: ScheduleChangePayload) -> Dict[str, Any]:
        """Schedules change implementation window."""
        self.get_change(change_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE itsm_changes
                SET scheduled_start = ?,
                    scheduled_end = ?,
                    status = 'scheduled'
                WHERE id = ?
            """, (payload.scheduled_start, payload.scheduled_end, change_id))
        return self.get_change(change_id)

    def transition_change(self, change_id: int, payload: ChangeTransitionPayload) -> Dict[str, Any]:
        """Transitions change lifecycle (implementing, review, closed, canceled)."""
        valid_transitions = {"implementing", "review", "closed", "canceled", "planning", "draft"}
        target = payload.target_status.lower().strip()
        if target not in valid_transitions:
            raise HTTPException(status_code=400, detail=f"Invalid transition target '{target}'. Allowed: {valid_transitions}")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE itsm_changes SET status = ? WHERE id = ?", (target, change_id))

        return self.get_change(change_id)

    # =========================================================================
    # 3. RELEASE & DEPLOYMENT MANAGEMENT
    # =========================================================================

    def create_release(self, payload: ReleaseCreate) -> Dict[str, Any]:
        rel_num = self._next_number("itsm_releases", "REL")
        created = now_iso()
        stage = payload.stage or "planning"
        actual_date = created if stage == "completed" else None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO itsm_releases
                (release_number, title, release_type, stage, version, release_notes, planned_date, actual_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rel_num, payload.title, payload.release_type or "minor", stage,
                payload.version, payload.release_notes or "", payload.planned_date, actual_date, created
            ))
            release_id = cursor.lastrowid

        return self.get_release(release_id)

    def get_release(self, release_id_or_number: Union[int, str]) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(release_id_or_number, int) or (isinstance(release_id_or_number, str) and release_id_or_number.isdigit()):
                cursor.execute("SELECT * FROM itsm_releases WHERE id = ?", (int(release_id_or_number),))
            else:
                cursor.execute("SELECT * FROM itsm_releases WHERE release_number = ?", (str(release_id_or_number),))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Release {release_id_or_number} not found.")
            return dict(row)

    def list_releases(
        self,
        stage: Optional[str] = None,
        release_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if stage:
            clauses.append("stage = ?")
            params.append(stage)
        if release_type:
            clauses.append("release_type = ?")
            params.append(release_type)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM itsm_releases {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]

    def update_release(self, release_id: int, payload: ReleaseUpdate) -> Dict[str, Any]:
        self.get_release(release_id)
        updates = []
        params = []

        fields = {
            "title": payload.title,
            "version": payload.version,
            "release_type": payload.release_type,
            "stage": payload.stage,
            "release_notes": payload.release_notes,
            "planned_date": payload.planned_date,
            "actual_date": payload.actual_date,
        }
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = ?")
                params.append(v)

        if updates:
            params.append(release_id)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE itsm_releases SET {', '.join(updates)} WHERE id = ?", params)

        return self.get_release(release_id)

    def set_release_stage(self, release_id: int, payload: ReleaseStagePayload) -> Dict[str, Any]:
        """Advances release stage (planning -> development -> testing -> deployment -> completed)."""
        valid_stages = ("planning", "development", "testing", "deployment", "completed")
        st = payload.stage.lower().strip()
        if st not in valid_stages:
            raise HTTPException(status_code=400, detail=f"Invalid release stage '{st}'. Allowed: {valid_stages}")

        actual_date_clause = ", actual_date = ?" if st == "completed" else ""
        params = [st]
        if st == "completed":
            params.append(now_iso())
        params.append(release_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE itsm_releases SET stage = ? {actual_date_clause} WHERE id = ?", params)

        return self.get_release(release_id)

    def delete_release(self, release_id: int) -> bool:
        self.get_release(release_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM itsm_releases WHERE id = ?", (release_id,))
            return cursor.rowcount > 0

    # =========================================================================
    # 4. SERVICE CATALOG & SERVICE REQUESTS
    # =========================================================================

    def create_catalog_item(self, payload: CatalogItemCreate) -> Dict[str, Any]:
        created = now_iso()
        fields_str = json.dumps(payload.form_fields or [])
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO itsm_catalog_items
                (name, category, description, icon, estimated_days, cost, form_fields_json, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payload.name, payload.category, payload.description or "", payload.icon or "package",
                payload.estimated_days or 1, payload.cost or 0.0, fields_str, 1 if payload.is_active else 0, created
            ))
            item_id = cursor.lastrowid
        return self.get_catalog_item(item_id)

    def get_catalog_item(self, item_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM itsm_catalog_items WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Catalog item {item_id} not found.")
            res = dict(row)
            try:
                res["form_fields"] = json.loads(res.get("form_fields_json") or "[]")
            except Exception:
                res["form_fields"] = []
            res["is_active"] = bool(res.get("is_active"))
            return res

    def list_catalog_items(self, category: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if is_active is not None:
            clauses.append("is_active = ?")
            params.append(1 if is_active else 0)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM itsm_catalog_items {where_sql} ORDER BY category ASC, name ASC"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            results = []
            for r in cursor.fetchall():
                item = dict(r)
                try:
                    item["form_fields"] = json.loads(item.get("form_fields_json") or "[]")
                except Exception:
                    item["form_fields"] = []
                item["is_active"] = bool(item.get("is_active"))
                results.append(item)
            return results

    def update_catalog_item(self, item_id: int, payload: CatalogItemUpdate) -> Dict[str, Any]:
        self.get_catalog_item(item_id)
        updates = []
        params = []
        fields = {
            "name": payload.name,
            "category": payload.category,
            "description": payload.description,
            "icon": payload.icon,
            "estimated_days": payload.estimated_days,
            "cost": payload.cost,
        }
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = ?")
                params.append(v)
        if payload.form_fields is not None:
            updates.append("form_fields_json = ?")
            params.append(json.dumps(payload.form_fields))
        if payload.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if payload.is_active else 0)

        if updates:
            params.append(item_id)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE itsm_catalog_items SET {', '.join(updates)} WHERE id = ?", params)

        return self.get_catalog_item(item_id)

    def delete_catalog_item(self, item_id: int) -> bool:
        self.get_catalog_item(item_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM itsm_catalog_items WHERE id = ?", (item_id,))
            return cursor.rowcount > 0

    def submit_service_request(self, payload: ServiceRequestCreate) -> Dict[str, Any]:
        """Submits a new service request against a catalog item."""
        cat_item = self.get_catalog_item(payload.catalog_item_id)
        req_num = self._next_number("itsm_service_requests", "REQ")
        created = now_iso()
        form_data_str = json.dumps(payload.form_data or {})

        # Default starting status: approval_pending if item costs > 0, else submitted
        initial_status = "approval_pending" if cat_item.get("cost", 0) > 0 else "submitted"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO itsm_service_requests
                (request_number, catalog_item_id, requester_name, requester_email, status, form_data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                req_num, payload.catalog_item_id, payload.requester_name, payload.requester_email,
                initial_status, form_data_str, created
            ))
            req_id = cursor.lastrowid

        return self.get_service_request(req_id)

    def get_service_request(self, request_id_or_number: Union[int, str]) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(request_id_or_number, int) or (isinstance(request_id_or_number, str) and request_id_or_number.isdigit()):
                cursor.execute("""
                    SELECT r.*, c.name AS catalog_item_name, c.category AS catalog_item_category, c.cost AS catalog_item_cost
                    FROM itsm_service_requests r
                    LEFT JOIN itsm_catalog_items c ON r.catalog_item_id = c.id
                    WHERE r.id = ?
                """, (int(request_id_or_number),))
            else:
                cursor.execute("""
                    SELECT r.*, c.name AS catalog_item_name, c.category AS catalog_item_category, c.cost AS catalog_item_cost
                    FROM itsm_service_requests r
                    LEFT JOIN itsm_catalog_items c ON r.catalog_item_id = c.id
                    WHERE r.request_number = ?
                """, (str(request_id_or_number),))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Service request {request_id_or_number} not found.")

            res = dict(row)
            try:
                res["form_data"] = json.loads(res.get("form_data_json") or "{}")
            except Exception:
                res["form_data"] = {}
            return res

    def list_service_requests(
        self,
        status: Optional[str] = None,
        catalog_item_id: Optional[int] = None,
        requester_email: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if status:
            clauses.append("r.status = ?")
            params.append(status)
        if catalog_item_id:
            clauses.append("r.catalog_item_id = ?")
            params.append(catalog_item_id)
        if requester_email:
            clauses.append("r.requester_email = ?")
            params.append(requester_email)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT r.*, c.name AS catalog_item_name, c.category AS catalog_item_category, c.cost AS catalog_item_cost
            FROM itsm_service_requests r
            LEFT JOIN itsm_catalog_items c ON r.catalog_item_id = c.id
            {where_sql}
            ORDER BY r.id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                res = dict(row)
                try:
                    res["form_data"] = json.loads(res.get("form_data_json") or "{}")
                except Exception:
                    res["form_data"] = {}
                results.append(res)
            return results

    def update_service_request_status(self, request_id: int, payload: ServiceRequestStatusUpdate) -> Dict[str, Any]:
        """Transitions service request status (submitted -> approval_pending -> fulfilling -> completed / rejected)."""
        valid_statuses = ("submitted", "approval_pending", "fulfilling", "completed", "rejected")
        st = payload.status.lower().strip()
        if st not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status '{st}'. Allowed: {valid_statuses}")

        completed_clause = ", completed_at = ?" if st == "completed" else ""
        params = [st]
        if st == "completed":
            params.append(now_iso())
        params.append(request_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE itsm_service_requests SET status = ? {completed_clause} WHERE id = ?", params)

        return self.get_service_request(request_id)

    # =========================================================================
    # 5. KNOWLEDGE MANAGEMENT (KCS) & DEFLECTION ENGINE
    # =========================================================================

    def create_knowledge_article(self, payload: KnowledgeArticleCreate) -> Dict[str, Any]:
        art_num = self._next_number("itsm_knowledge_articles", "KB")
        created = now_iso()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO itsm_knowledge_articles
                (article_number, title, content_html, category, tags, status, view_count, helpful_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """, (
                art_num, payload.title, payload.content_html, payload.category or "General",
                payload.tags or "", payload.status or "published", created, created
            ))
            art_id = cursor.lastrowid
        return self.get_knowledge_article(art_id)

    def get_knowledge_article(self, article_id_or_number: Union[int, str], increment_views: bool = False) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(article_id_or_number, int) or (isinstance(article_id_or_number, str) and article_id_or_number.isdigit()):
                cursor.execute("SELECT * FROM itsm_knowledge_articles WHERE id = ?", (int(article_id_or_number),))
            else:
                cursor.execute("SELECT * FROM itsm_knowledge_articles WHERE article_number = ?", (str(article_id_or_number),))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Knowledge article {article_id_or_number} not found.")

            art = dict(row)
            if increment_views:
                cursor.execute("UPDATE itsm_knowledge_articles SET view_count = view_count + 1 WHERE id = ?", (art["id"],))
                art["view_count"] += 1
            return art

    def update_knowledge_article(self, article_id: int, payload: KnowledgeArticleUpdate) -> Dict[str, Any]:
        self.get_knowledge_article(article_id)
        updates = ["updated_at = ?"]
        params = [now_iso()]

        fields = {
            "title": payload.title,
            "content_html": payload.content_html,
            "category": payload.category,
            "tags": payload.tags,
            "status": payload.status,
        }
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = ?")
                params.append(v)

        params.append(article_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE itsm_knowledge_articles SET {', '.join(updates)} WHERE id = ?", params)

        return self.get_knowledge_article(article_id)

    def delete_knowledge_article(self, article_id: int) -> bool:
        self.get_knowledge_article(article_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM itsm_knowledge_articles WHERE id = ?", (article_id,))
            return cursor.rowcount > 0

    def mark_article_helpful(self, article_id: int) -> Dict[str, Any]:
        self.get_knowledge_article(article_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE itsm_knowledge_articles SET helpful_count = helpful_count + 1 WHERE id = ?", (article_id,))
        return self.get_knowledge_article(article_id)

    mark_helpful_article = mark_article_helpful

    def list_knowledge_articles(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if category:
            clauses.append("category = ?")
            params.append(category)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM itsm_knowledge_articles {where_sql} ORDER BY helpful_count DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            results = [dict(r) for r in rows]

            if query:
                q_tokens = [t.lower() for t in re.findall(r"\w+", query)]
                filtered = []
                for a in results:
                    content = f"{a['article_number']} {a['title']} {a['tags']} {a['content_html']}".lower()
                    if any(t in content for t in q_tokens):
                        filtered.append(a)
                return filtered
            return results

    def search_deflection(self, title: str, description: str = "", category: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        """Incident Deflection Matching Algorithm.
        Analyzes keywords from prospective incident ticket against published articles and
        computes deflection relevance scores (weights: title match 3x, tag match 4x, body match 1x).
        """
        combined_text = f"{title} {description} {category}".lower()
        query_words = set(re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", combined_text))
        # Filter common stopwords
        stopwords = {"the", "and", "for", "with", "this", "that", "from", "have", "not", "are", "you", "can"}
        query_tokens = query_words - stopwords

        if not query_tokens:
            return []

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM itsm_knowledge_articles WHERE status = 'published'")
            articles = [dict(r) for r in cursor.fetchall()]

        scored_articles = []
        for art in articles:
            score = 0
            title_lower = art["title"].lower()
            tags_lower = (art.get("tags") or "").lower()
            body_lower = art["content_html"].lower()

            for token in query_tokens:
                if token in tags_lower:
                    score += 4
                if token in title_lower:
                    score += 3
                if token in body_lower:
                    score += 1

            if score > 0:
                art["deflection_score"] = score
                # Strip HTML tags for clean snippet preview
                clean_snippet = re.sub(r"<[^>]+>", " ", art["content_html"])[:250].strip() + "..."
                art["snippet"] = clean_snippet
                scored_articles.append(art)

        scored_articles.sort(key=lambda x: (x["deflection_score"], x["helpful_count"]), reverse=True)
        return scored_articles[:limit]

    # =========================================================================
    # 6. ASSET & ITAM CONTRACTS MANAGEMENT
    # =========================================================================

    def create_software_license(self, payload: SoftwareLicenseCreate) -> Dict[str, Any]:
        created = now_iso()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO itsm_software_licenses
                (software_name, vendor, total_seats, allocated_seats, license_key, expiry_date, cost, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payload.software_name, payload.vendor, payload.total_seats,
                payload.allocated_seats or 0, payload.license_key or "",
                payload.expiry_date, payload.cost or 0.0, created
            ))
            lic_id = cursor.lastrowid
        return self.get_software_license(lic_id)

    def get_software_license(self, license_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM itsm_software_licenses WHERE id = ?", (license_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Software license {license_id} not found.")
            res = dict(row)
            res["available_seats"] = max(0, res["total_seats"] - res["allocated_seats"])
            res["utilization_pct"] = round((res["allocated_seats"] / res["total_seats"] * 100), 1) if res["total_seats"] > 0 else 0.0
            return res

    def list_software_licenses(self, vendor: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if vendor:
            clauses.append("vendor LIKE ?")
            params.append(f"%{vendor}%")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM itsm_software_licenses {where_sql} ORDER BY id ASC"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            results = []
            for r in cursor.fetchall():
                lic = dict(r)
                lic["available_seats"] = max(0, lic["total_seats"] - lic["allocated_seats"])
                lic["utilization_pct"] = round((lic["allocated_seats"] / lic["total_seats"] * 100), 1) if lic["total_seats"] > 0 else 0.0
                results.append(lic)
            return results

    def update_software_license(self, license_id: int, payload: SoftwareLicenseUpdate) -> Dict[str, Any]:
        self.get_software_license(license_id)
        updates = []
        params = []
        fields = {
            "software_name": payload.software_name,
            "vendor": payload.vendor,
            "total_seats": payload.total_seats,
            "allocated_seats": payload.allocated_seats,
            "license_key": payload.license_key,
            "expiry_date": payload.expiry_date,
            "cost": payload.cost,
        }
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = ?")
                params.append(v)

        if updates:
            params.append(license_id)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE itsm_software_licenses SET {', '.join(updates)} WHERE id = ?", params)

        return self.get_software_license(license_id)

    def allocate_license_seats(self, license_id: int, seats: int = 1) -> Dict[str, Any]:
        lic = self.get_software_license(license_id)
        if lic["allocated_seats"] + seats > lic["total_seats"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot allocate {seats} seats. Only {lic['available_seats']} available out of {lic['total_seats']} total."
            )

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE itsm_software_licenses SET allocated_seats = allocated_seats + ? WHERE id = ?", (seats, license_id))

        return self.get_software_license(license_id)

    def release_license_seats(self, license_id: int, seats: int = 1) -> Dict[str, Any]:
        lic = self.get_software_license(license_id)
        if lic["allocated_seats"] - seats < 0:
            raise HTTPException(status_code=400, detail="Cannot release more seats than currently allocated.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE itsm_software_licenses SET allocated_seats = allocated_seats - ? WHERE id = ?", (seats, license_id))

        return self.get_software_license(license_id)

    def delete_software_license(self, license_id: int) -> bool:
        self.get_software_license(license_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM itsm_software_licenses WHERE id = ?", (license_id,))
            return cursor.rowcount > 0

    def create_vendor_contract(self, payload: VendorContractCreate) -> Dict[str, Any]:
        created = now_iso()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO itsm_vendor_contracts
                (vendor_name, contract_type, start_date, end_date, annual_cost, sla_terms, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payload.vendor_name, payload.contract_type or "SaaS", payload.start_date,
                payload.end_date, payload.annual_cost or 0.0, payload.sla_terms or "",
                payload.status or "active", created
            ))
            contract_id = cursor.lastrowid
        return self.get_vendor_contract(contract_id)

    def get_vendor_contract(self, contract_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM itsm_vendor_contracts WHERE id = ?", (contract_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Vendor contract {contract_id} not found.")
            return dict(row)

    def list_vendor_contracts(
        self,
        status: Optional[str] = None,
        vendor: Optional[str] = None,
        expiring_days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        clauses = []
        params = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if vendor:
            clauses.append("vendor_name LIKE ?")
            params.append(f"%{vendor}%")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM itsm_vendor_contracts {where_sql} ORDER BY end_date ASC"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = [dict(r) for r in cursor.fetchall()]

            if expiring_days is not None:
                now_date = datetime.date.today()
                cutoff = now_date + datetime.timedelta(days=expiring_days)
                filtered = []
                for c in rows:
                    try:
                        end_d = datetime.date.fromisoformat(c["end_date"][:10])
                        if now_date <= end_d <= cutoff:
                            c["days_until_expiration"] = (end_d - now_date).days
                            filtered.append(c)
                    except Exception:
                        pass
                return filtered

            return rows

    def update_vendor_contract(self, contract_id: int, payload: VendorContractUpdate) -> Dict[str, Any]:
        self.get_vendor_contract(contract_id)
        updates = []
        params = []
        fields = {
            "vendor_name": payload.vendor_name,
            "contract_type": payload.contract_type,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "annual_cost": payload.annual_cost,
            "sla_terms": payload.sla_terms,
            "status": payload.status,
        }
        for k, v in fields.items():
            if v is not None:
                updates.append(f"{k} = ?")
                params.append(v)

        if updates:
            params.append(contract_id)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE itsm_vendor_contracts SET {', '.join(updates)} WHERE id = ?", params)

        return self.get_vendor_contract(contract_id)

    def delete_vendor_contract(self, contract_id: int) -> bool:
        self.get_vendor_contract(contract_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM itsm_vendor_contracts WHERE id = ?", (contract_id,))
            return cursor.rowcount > 0

    def get_itam_summary(self) -> Dict[str, Any]:
        """Provides executive ITAM intelligence: license spend, contracts spend, upcoming expirations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # License stats
            cursor.execute("SELECT SUM(cost) AS total_lic_cost, SUM(total_seats) AS total_seats, SUM(allocated_seats) AS allocated_seats FROM itsm_software_licenses")
            lic_stats = cursor.fetchone()
            total_lic_spend = lic_stats["total_lic_cost"] or 0.0
            tot_seats = lic_stats["total_seats"] or 0
            alloc_seats = lic_stats["allocated_seats"] or 0
            overall_util = round((alloc_seats / tot_seats * 100), 1) if tot_seats > 0 else 0.0

            # Contracts stats
            cursor.execute("SELECT SUM(annual_cost) AS total_contract_cost, COUNT(*) AS active_contract_count FROM itsm_vendor_contracts WHERE status = 'active'")
            cont_stats = cursor.fetchone()
            total_cont_spend = cont_stats["total_contract_cost"] or 0.0
            active_contracts = cont_stats["active_contract_count"] or 0

            # Expiring contracts (within 90 days)
            now_d = datetime.date.today()
            cutoff_90 = (now_d + datetime.timedelta(days=90)).isoformat()
            cursor.execute("""
                SELECT id, vendor_name, contract_type, end_date, annual_cost
                FROM itsm_vendor_contracts
                WHERE status = 'active' AND end_date <= ? AND end_date >= ?
                ORDER BY end_date ASC
            """, (cutoff_90, now_d.isoformat()))
            expiring_90 = [dict(r) for r in cursor.fetchall()]

            # Over-utilized licenses (>= 90% utilization)
            cursor.execute("""
                SELECT id, software_name, vendor, total_seats, allocated_seats
                FROM itsm_software_licenses
                WHERE total_seats > 0 AND (CAST(allocated_seats AS REAL) / total_seats) >= 0.90
            """)
            near_capacity_lics = [dict(r) for r in cursor.fetchall()]

        return {
            "total_annual_contract_spend": total_cont_spend,
            "total_software_license_spend": total_lic_spend,
            "total_combined_itam_spend": total_cont_spend + total_lic_spend,
            "active_contracts_count": active_contracts,
            "total_licensed_seats": tot_seats,
            "allocated_licensed_seats": alloc_seats,
            "overall_seat_utilization_pct": overall_util,
            "contracts_expiring_within_90_days": expiring_90,
            "near_capacity_licenses": near_capacity_lics,
        }


# Global engine singleton
itsm_engine = FullITSMEngine()


# ============================================================================
# FASTAPI ROUTERS (API V2)
# ============================================================================

itsm_router = APIRouter()

# ----------------------------------------------------------------------------
# 1. Problem Management Endpoints (/api/v2/problems)
# ----------------------------------------------------------------------------
problems_router = APIRouter(prefix="/api/v2/problems", tags=["Problem Management & KEDB"])

@problems_router.get("", response_model=List[Dict[str, Any]])
def list_problems_endpoint(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    kedb_published: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return itsm_engine.list_problems(status=status, category=category, priority=priority, kedb_published=kedb_published, limit=limit, offset=offset)

@problems_router.post("", status_code=status.HTTP_201_CREATED)
def create_problem_endpoint(payload: ProblemCreate):
    return itsm_engine.create_problem(payload)

@problems_router.get("/kedb/search")
def search_kedb_endpoint(query: str = Query("", description="Keywords to match in Known Error Database"), category: Optional[str] = None):
    return itsm_engine.search_kedb(query=query, category=category)

@problems_router.get("/{problem_id}")
def get_problem_endpoint(problem_id: str):
    return itsm_engine.get_problem(problem_id)

@problems_router.put("/{problem_id}")
def update_problem_endpoint(problem_id: int, payload: ProblemUpdate):
    return itsm_engine.update_problem(problem_id, payload)

@problems_router.delete("/{problem_id}")
def delete_problem_endpoint(problem_id: int):
    success = itsm_engine.delete_problem(problem_id)
    return {"success": success, "deleted_id": problem_id}

@problems_router.post("/{problem_id}/link-incidents")
def link_incidents_endpoint(problem_id: int, payload: LinkIncidentsPayload):
    return itsm_engine.link_incidents(problem_id, payload.incident_ids)

@problems_router.post("/{problem_id}/unlink-incident")
def unlink_incident_endpoint(problem_id: int, incident_id: str = Query(...)):
    return itsm_engine.unlink_incident(problem_id, incident_id)

@problems_router.post("/{problem_id}/publish-kedb")
def publish_kedb_endpoint(problem_id: int, payload: PublishKEDBPayload):
    return itsm_engine.publish_to_kedb(problem_id, payload)

@problems_router.post("/{problem_id}/resolve")
def resolve_problem_endpoint(problem_id: int, payload: ProblemResolvePayload):
    return itsm_engine.resolve_problem(problem_id, payload)


# ----------------------------------------------------------------------------
# 2. Change Management Endpoints (/api/v2/changes)
# ----------------------------------------------------------------------------
changes_router = APIRouter(prefix="/api/v2/changes", tags=["Change Management & CAB"])

@changes_router.get("", response_model=List[Dict[str, Any]])
def list_changes_endpoint(
    change_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    cab_required: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return itsm_engine.list_changes(change_type=change_type, status=status, risk_level=risk_level, cab_required=cab_required, limit=limit, offset=offset)

@changes_router.post("", status_code=status.HTTP_201_CREATED)
def create_change_endpoint(payload: ChangeCreate):
    return itsm_engine.create_change(payload)

@changes_router.get("/{change_id}")
def get_change_endpoint(change_id: str):
    return itsm_engine.get_change(change_id)

@changes_router.put("/{change_id}")
def update_change_endpoint(change_id: int, payload: ChangeUpdate):
    return itsm_engine.update_change(change_id, payload)

@changes_router.delete("/{change_id}")
def delete_change_endpoint(change_id: int):
    success = itsm_engine.delete_change(change_id)
    return {"success": success, "deleted_id": change_id}

@changes_router.post("/{change_id}/risk-assessment")
def assess_risk_endpoint(change_id: int, payload: RiskAssessmentPayload):
    return itsm_engine.assess_risk(change_id, payload)

@changes_router.post("/{change_id}/submit-cab")
def submit_cab_endpoint(change_id: int, payload: SubmitCABPayload):
    return itsm_engine.submit_to_cab(change_id, payload)

@changes_router.post("/{change_id}/cab-vote")
def cab_vote_endpoint(change_id: int, payload: CABVotePayload):
    return itsm_engine.cast_cab_vote(change_id, payload)

@changes_router.post("/{change_id}/schedule")
def schedule_change_endpoint(change_id: int, payload: ScheduleChangePayload):
    return itsm_engine.schedule_change(change_id, payload)

@changes_router.post("/{change_id}/transition")
def transition_change_endpoint(change_id: int, payload: ChangeTransitionPayload):
    return itsm_engine.transition_change(change_id, payload)


# ----------------------------------------------------------------------------
# 3. Release & Deployment Endpoints (/api/v2/releases)
# ----------------------------------------------------------------------------
releases_router = APIRouter(prefix="/api/v2/releases", tags=["Release & Deployment"])

@releases_router.get("", response_model=List[Dict[str, Any]])
def list_releases_endpoint(
    stage: Optional[str] = Query(None),
    release_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return itsm_engine.list_releases(stage=stage, release_type=release_type, limit=limit, offset=offset)

@releases_router.post("", status_code=status.HTTP_201_CREATED)
def create_release_endpoint(payload: ReleaseCreate):
    return itsm_engine.create_release(payload)

@releases_router.get("/{release_id}")
def get_release_endpoint(release_id: str):
    return itsm_engine.get_release(release_id)

@releases_router.put("/{release_id}")
def update_release_endpoint(release_id: int, payload: ReleaseUpdate):
    return itsm_engine.update_release(release_id, payload)

@releases_router.delete("/{release_id}")
def delete_release_endpoint(release_id: int):
    success = itsm_engine.delete_release(release_id)
    return {"success": success, "deleted_id": release_id}

@releases_router.post("/{release_id}/stage")
def set_release_stage_endpoint(release_id: int, payload: ReleaseStagePayload):
    return itsm_engine.set_release_stage(release_id, payload)


# ----------------------------------------------------------------------------
# 4. Service Catalog & Service Requests (/api/v2/catalog & /api/v2/requests)
# ----------------------------------------------------------------------------
catalog_router = APIRouter(prefix="/api/v2/catalog", tags=["Service Catalog"])

@catalog_router.get("", response_model=List[Dict[str, Any]])
def list_catalog_endpoint(category: Optional[str] = Query(None), is_active: Optional[bool] = Query(None)):
    return itsm_engine.list_catalog_items(category=category, is_active=is_active)

@catalog_router.post("", status_code=status.HTTP_201_CREATED)
def create_catalog_endpoint(payload: CatalogItemCreate):
    return itsm_engine.create_catalog_item(payload)

@catalog_router.get("/{item_id}")
def get_catalog_endpoint(item_id: int):
    return itsm_engine.get_catalog_item(item_id)

@catalog_router.put("/{item_id}")
def update_catalog_endpoint(item_id: int, payload: CatalogItemUpdate):
    return itsm_engine.update_catalog_item(item_id, payload)

@catalog_router.delete("/{item_id}")
def delete_catalog_endpoint(item_id: int):
    success = itsm_engine.delete_catalog_item(item_id)
    return {"success": success, "deleted_id": item_id}


requests_router = APIRouter(prefix="/api/v2/requests", tags=["Service Requests"])

@requests_router.get("", response_model=List[Dict[str, Any]])
def list_requests_endpoint(
    status: Optional[str] = Query(None),
    catalog_item_id: Optional[int] = Query(None),
    requester_email: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return itsm_engine.list_service_requests(status=status, catalog_item_id=catalog_item_id, requester_email=requester_email, limit=limit, offset=offset)

@requests_router.post("", status_code=status.HTTP_201_CREATED)
def create_request_endpoint(payload: ServiceRequestCreate):
    return itsm_engine.submit_service_request(payload)

@requests_router.get("/{request_id}")
def get_request_endpoint(request_id: str):
    return itsm_engine.get_service_request(request_id)

@requests_router.put("/{request_id}/status")
def update_request_status_endpoint(request_id: int, payload: ServiceRequestStatusUpdate):
    return itsm_engine.update_service_request_status(request_id, payload)


# ----------------------------------------------------------------------------
# 5. Knowledge Management Endpoints (/api/v2/knowledge)
# ----------------------------------------------------------------------------
knowledge_router = APIRouter(prefix="/api/v2/knowledge", tags=["Knowledge Management (KCS)"])

@knowledge_router.get("", response_model=List[Dict[str, Any]])
def list_articles_endpoint(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return itsm_engine.list_knowledge_articles(status=status, category=category, query=query, limit=limit, offset=offset)

@knowledge_router.post("", status_code=status.HTTP_201_CREATED)
def create_article_endpoint(payload: KnowledgeArticleCreate):
    return itsm_engine.create_knowledge_article(payload)

@knowledge_router.get("/search/deflection")
def search_deflection_endpoint(
    title: str = Query(..., min_length=2, description="Proposed issue title"),
    description: str = Query("", description="Issue description"),
    category: str = Query("", description="Issue category"),
    limit: int = Query(5, ge=1, le=10),
):
    return itsm_engine.search_deflection(title=title, description=description, category=category, limit=limit)

@knowledge_router.get("/{article_id}")
def get_article_endpoint(article_id: str, view: bool = Query(True, description="Increment view counter")):
    return itsm_engine.get_knowledge_article(article_id, increment_views=view)

@knowledge_router.put("/{article_id}")
def update_article_endpoint(article_id: int, payload: KnowledgeArticleUpdate):
    return itsm_engine.update_knowledge_article(article_id, payload)

@knowledge_router.delete("/{article_id}")
def delete_article_endpoint(article_id: int):
    success = itsm_engine.delete_knowledge_article(article_id)
    return {"success": success, "deleted_id": article_id}

@knowledge_router.post("/{article_id}/helpful")
def mark_helpful_endpoint(article_id: int):
    return itsm_engine.mark_helpful_article(article_id)


# ----------------------------------------------------------------------------
# 6. Asset & ITAM Contracts Endpoints (/api/v2/assets/contracts)
# ----------------------------------------------------------------------------
assets_router = APIRouter(prefix="/api/v2/assets/contracts", tags=["ITAM Software Licenses & Contracts"])

@assets_router.get("/licenses", response_model=List[Dict[str, Any]])
def list_licenses_endpoint(vendor: Optional[str] = Query(None)):
    return itsm_engine.list_software_licenses(vendor=vendor)

@assets_router.post("/licenses", status_code=status.HTTP_201_CREATED)
def create_license_endpoint(payload: SoftwareLicenseCreate):
    return itsm_engine.create_software_license(payload)

@assets_router.get("/licenses/{license_id}")
def get_license_endpoint(license_id: int):
    return itsm_engine.get_software_license(license_id)

@assets_router.put("/licenses/{license_id}")
def update_license_endpoint(license_id: int, payload: SoftwareLicenseUpdate):
    return itsm_engine.update_software_license(license_id, payload)

@assets_router.delete("/licenses/{license_id}")
def delete_license_endpoint(license_id: int):
    success = itsm_engine.delete_software_license(license_id)
    return {"success": success, "deleted_id": license_id}

@assets_router.post("/licenses/{license_id}/allocate")
def allocate_seats_endpoint(license_id: int, payload: LicenseSeatAction):
    return itsm_engine.allocate_license_seats(license_id, payload.seats)

@assets_router.post("/licenses/{license_id}/release")
def release_seats_endpoint(license_id: int, payload: LicenseSeatAction):
    return itsm_engine.release_license_seats(license_id, payload.seats)

@assets_router.get("/contracts", response_model=List[Dict[str, Any]])
def list_contracts_endpoint(
    status: Optional[str] = Query(None),
    vendor: Optional[str] = Query(None),
    expiring_days: Optional[int] = Query(None, description="Filter contracts expiring within N days"),
):
    return itsm_engine.list_vendor_contracts(status=status, vendor=vendor, expiring_days=expiring_days)

@assets_router.post("/contracts", status_code=status.HTTP_201_CREATED)
def create_contract_endpoint(payload: VendorContractCreate):
    return itsm_engine.create_vendor_contract(payload)

@assets_router.get("/contracts/{contract_id}")
def get_contract_endpoint(contract_id: int):
    return itsm_engine.get_vendor_contract(contract_id)

@assets_router.put("/contracts/{contract_id}")
def update_contract_endpoint(contract_id: int, payload: VendorContractUpdate):
    return itsm_engine.update_vendor_contract(contract_id, payload)

@assets_router.delete("/contracts/{contract_id}")
def delete_contract_endpoint(contract_id: int):
    success = itsm_engine.delete_vendor_contract(contract_id)
    return {"success": success, "deleted_id": contract_id}

@assets_router.get("/summary")
def get_itam_summary_endpoint():
    return itsm_engine.get_itam_summary()


# Mount all sub-routers onto master itsm_router
itsm_router.include_router(problems_router)
itsm_router.include_router(changes_router)
itsm_router.include_router(releases_router)
itsm_router.include_router(catalog_router)
itsm_router.include_router(requests_router)
itsm_router.include_router(knowledge_router)
itsm_router.include_router(assets_router)


# ============================================================================
# COMPREHENSIVE UNIT TEST SUITE
# ============================================================================

class TestFullITSMEngine(unittest.TestCase):
    """Rigorous unit test suite testing all ITIL modules and edge cases in isolated SQLite storage."""

    def setUp(self):
        self.engine = FullITSMEngine(db_path=":memory:")

    def tearDown(self):
        self.engine.close()

    # 1. Problem Management & KEDB Tests
    def test_problem_lifecycle_and_kedb(self):
        # Create problem
        prob = self.engine.create_problem(ProblemCreate(
            title="Redis Connection Leak Under High Concurrency",
            description="Microservices reporting Redis connection pool exhaustion during peak hours.",
            category="Database",
            priority="P1",
            five_whys=[
                {"why": 1, "answer": "Redis connection pool max capacity reached"},
                {"why": 2, "answer": "HTTP client connections not being released on exception"},
                {"why": 3, "answer": "Missing finally block in billing checkout controller"},
            ],
            workaround="Restart pgbouncer and flush expired idle client sessions",
        ))
        self.assertTrue(prob["problem_number"].startswith("PRB"))
        self.assertEqual(prob["status"], "open")
        self.assertEqual(len(prob["five_whys"]), 3)

        # Link incidents
        link_res = self.engine.link_incidents(prob["id"], ["INC00101", "INC00102", "INC00103"])
        self.assertEqual(link_res["linked_new_incidents"], 3)
        updated = self.engine.get_problem(prob["id"])
        self.assertEqual(len(updated["linked_incidents"]), 3)

        # Publish to KEDB
        kedb_res = self.engine.publish_to_kedb(prob["id"], PublishKEDBPayload(
            kedb_published=True,
            workaround="Execute scripts/flush_redis_zombie_conns.sh"
        ))
        self.assertTrue(kedb_res["kedb_published"])
        self.assertEqual(kedb_res["status"], "known_error")

        # Verify KEDB search
        kedb_results = self.engine.search_kedb("Redis connection")
        self.assertTrue(any(k["problem_number"] == prob["problem_number"] for k in kedb_results))

        # Bulk resolve linked incidents
        resolve_res = self.engine.resolve_problem(prob["id"], ProblemResolvePayload(
            permanent_solution="Patched billing checkout microservice v2.4.1 to enforce connection release in context manager.",
            root_cause="Uncaught KeyError in JSON parser prevented execution of pool.release()",
            bulk_resolve_incidents=True
        ))
        self.assertEqual(resolve_res["problem"]["status"], "resolved")
        self.assertIsNotNone(resolve_res["problem"]["resolved_at"])
        self.assertEqual(resolve_res["count_resolved"], 3)

    # 2. Change Management & CAB Review Tests
    def test_change_risk_assessment_and_cab(self):
        # Create Change RFC
        change = self.engine.create_change(ChangeCreate(
            title="Upgrade Core Kubernetes Cluster from 1.28 to 1.30",
            description="Rolling upgrade of production EKS node groups and control planes.",
            change_type="normal",
            risk_level="medium",
            implementation_plan="1. Upgrade control plane. 2. Drain node group alpha. 3. Upgrade node group beta.",
            backout_plan="Rollback to previous launch template snapshot and restore etcd snapshot.",
            test_plan="Execute synthetic integration smoke tests suite.",
        ))
        self.assertTrue(change["change_number"].startswith("CHG"))
        self.assertEqual(change["status"], "draft")

        # Perform Risk Assessment Questionnaire
        assessed = self.engine.assess_risk(change["id"], RiskAssessmentPayload(
            scope="enterprise",              # 5
            downtime="under_1h",             # 2
            reversibility="moderate_rollback",# 3
            testing="automated_tested",       # 1
            data_impact="schema_migration"    # 3 => Total = 14 -> high
        ))
        self.assertEqual(assessed["risk_level"], "high")
        self.assertTrue(assessed["cab_required"])

        # Submit to CAB
        submitted = self.engine.submit_to_cab(change["id"], SubmitCABPayload())
        chg_cab = submitted["change"]
        self.assertEqual(chg_cab["status"], "cab_review")
        self.assertEqual(len(chg_cab["approvals"]), 3)

        # Cast CAB Votes
        vote1 = self.engine.cast_cab_vote(change["id"], CABVotePayload(
            approver_name="Enterprise CAB Chair",
            approver_role="CAB Chair",
            decision="approved",
            comments="Maintenance window confirmed for Sunday 02:00 UTC."
        ))
        self.assertFalse(vote1["all_approved"])

        vote2 = self.engine.cast_cab_vote(change["id"], CABVotePayload(
            approver_name="Chief Information Security Officer",
            approver_role="Security Lead",
            decision="approved"
        ))
        vote3 = self.engine.cast_cab_vote(change["id"], CABVotePayload(
            approver_name="Infrastructure Operations Director",
            approver_role="Infra Lead",
            decision="approved"
        ))
        self.assertTrue(vote3["all_approved"])

        # Schedule Change
        scheduled = self.engine.schedule_change(change["id"], ScheduleChangePayload(
            scheduled_start="2026-11-01T02:00:00Z",
            scheduled_end="2026-11-01T04:00:00Z"
        ))
        self.assertEqual(scheduled["status"], "scheduled")

        # Advance to implementing then closed
        impl = self.engine.transition_change(change["id"], ChangeTransitionPayload(target_status="implementing"))
        self.assertEqual(impl["status"], "implementing")
        closed = self.engine.transition_change(change["id"], ChangeTransitionPayload(target_status="closed"))
        self.assertEqual(closed["status"], "closed")

    # 3. Release Management Tests
    def test_release_lifecycle(self):
        rel = self.engine.create_release(ReleaseCreate(
            title="Enterprise Platform Q4 Major Release",
            version="v3.0.0",
            release_type="major",
            release_notes="Includes new ITSM Suite, Autonomous CMDB, and AI Co-Pilot."
        ))
        self.assertTrue(rel["release_number"].startswith("REL"))
        self.assertEqual(rel["stage"], "planning")

        # Advance through stages
        for next_st in ("development", "testing", "deployment", "completed"):
            updated = self.engine.set_release_stage(rel["id"], ReleaseStagePayload(stage=next_st))
            self.assertEqual(updated["stage"], next_st)

        # When completed, actual_date must be populated
        self.assertIsNotNone(updated["actual_date"])

    # 4. Service Catalog & Request Tests
    def test_service_catalog_and_request_submission(self):
        # Pre-seeded items check
        items = self.engine.list_catalog_items()
        self.assertGreaterEqual(len(items), 4)

        laptop_item = next(i for i in items if "Laptop" in i["name"])
        self.assertGreater(laptop_item["cost"], 0)

        # Submit request
        req = self.engine.submit_service_request(ServiceRequestCreate(
            catalog_item_id=laptop_item["id"],
            requester_name="Alex Mercer",
            requester_email="alex.mercer@enterprise.corp",
            form_data={
                "os_preference": "macOS (M3 Pro 36GB)",
                "shipping_address": "742 Evergreen Terrace, Sector 4",
                "monitor_dock_required": True
            }
        ))
        self.assertTrue(req["request_number"].startswith("REQ"))
        self.assertEqual(req["status"], "approval_pending")
        self.assertEqual(req["form_data"]["os_preference"], "macOS (M3 Pro 36GB)")

        # Transition status
        fulfilling = self.engine.update_service_request_status(req["id"], ServiceRequestStatusUpdate(status="fulfilling"))
        self.assertEqual(fulfilling["status"], "fulfilling")

        completed = self.engine.update_service_request_status(req["id"], ServiceRequestStatusUpdate(status="completed"))
        self.assertEqual(completed["status"], "completed")
        self.assertIsNotNone(completed["completed_at"])

    # 5. Knowledge Management (KCS) & Deflection Tests
    def test_kcs_and_incident_deflection(self):
        # Verify pre-seeded articles
        articles = self.engine.list_knowledge_articles()
        self.assertGreaterEqual(len(articles), 4)

        # Test incident deflection query
        deflection_matches = self.engine.search_deflection(
            title="User unable to connect to WireGuard VPN due to DNS failure",
            description="DNS cannot resolve internal microservice endpoints when on remote wifi."
        )
        self.assertTrue(len(deflection_matches) > 0)
        top_match = deflection_matches[0]
        self.assertIn("WireGuard", top_match["title"])
        self.assertGreater(top_match["deflection_score"], 0)

        # View and helpful increment
        art_before = self.engine.get_knowledge_article(top_match["id"], increment_views=True)
        art_helpful = self.engine.mark_article_helpful(top_match["id"])
        self.assertEqual(art_helpful["helpful_count"], art_before["helpful_count"] + 1)

    # 6. Asset & ITAM Contracts Tests
    def test_itam_licenses_and_contracts(self):
        # Verify pre-seeded licenses
        licenses = self.engine.list_software_licenses()
        self.assertGreaterEqual(len(licenses), 4)

        jb_lic = next(l for l in licenses if "JetBrains" in l["software_name"])
        initial_alloc = jb_lic["allocated_seats"]

        # Allocate seat
        alloc_res = self.engine.allocate_license_seats(jb_lic["id"], 5)
        self.assertEqual(alloc_res["allocated_seats"], initial_alloc + 5)

        # Release seat
        rel_res = self.engine.release_license_seats(jb_lic["id"], 2)
        self.assertEqual(rel_res["allocated_seats"], initial_alloc + 3)

        # Verify pre-seeded contracts
        contracts = self.engine.list_vendor_contracts()
        self.assertGreaterEqual(len(contracts), 3)

        # Verify ITAM summary calculation
        summary = self.engine.get_itam_summary()
        self.assertGreater(summary["total_annual_contract_spend"], 0)
        self.assertGreater(summary["total_software_license_spend"], 0)
        self.assertGreater(summary["total_combined_itam_spend"], 0)
        self.assertGreater(summary["overall_seat_utilization_pct"], 50.0)


class TestFullITSMFastAPIRoutes(unittest.TestCase):
    """Integration test suite executing HTTP calls against all mounted ITSM endpoints."""

    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        test_app = FastAPI()
        test_app.include_router(itsm_router)
        self.client = TestClient(test_app)

    def test_api_problems(self):
        res = self.client.get("/api/v2/problems")
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/v2/problems", json={
            "title": "API Test Gateway Latency Spike",
            "description": "API latency spikes up to 4s under load.",
            "category": "Software",
            "priority": "P2",
            "workaround": "Scale gateway pods to 10 replicas"
        })
        self.assertEqual(res.status_code, 201)
        prob = res.json()
        prob_id = prob["id"]

        res = self.client.post(f"/api/v2/problems/{prob_id}/link-incidents", json={"incident_ids": ["INC9901", "INC9902"]})
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/api/v2/problems/{prob_id}/publish-kedb", json={"kedb_published": True})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["kedb_published"])

        res = self.client.get("/api/v2/problems/kedb/search?query=Gateway")
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/api/v2/problems/{prob_id}/resolve", json={
            "permanent_solution": "Upgraded Envoy proxy connection pooling buffer.",
            "bulk_resolve_incidents": True
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["problem"]["status"], "resolved")

    def test_api_changes_and_cab(self):
        res = self.client.post("/api/v2/changes", json={
            "title": "API Test Database Failover Drill",
            "change_type": "normal",
            "risk_level": "medium",
            "implementation_plan": "Failover to replica.",
            "backout_plan": "Failback to primary."
        })
        self.assertEqual(res.status_code, 201)
        chg = res.json()
        chg_id = chg["id"]

        res = self.client.post(f"/api/v2/changes/{chg_id}/risk-assessment", json={
            "scope": "enterprise",
            "downtime": "under_1h",
            "reversibility": "trivial_rollback",
            "testing": "automated_tested",
            "data_impact": "read_only"
        })
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/api/v2/changes/{chg_id}/submit-cab", json={})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["change"]["status"], "cab_review")

        res = self.client.post(f"/api/v2/changes/{chg_id}/cab-vote", json={
            "approver_name": "Enterprise CAB Chair",
            "approver_role": "CAB Chair",
            "decision": "approved",
            "comments": "Approved for drill window."
        })
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/api/v2/changes/{chg_id}/schedule", json={
            "scheduled_start": "2026-12-01T00:00:00Z",
            "scheduled_end": "2026-12-01T02:00:00Z"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "scheduled")

        res = self.client.post(f"/api/v2/changes/{chg_id}/transition", json={"target_status": "closed"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "closed")

    def test_api_releases(self):
        res = self.client.post("/api/v2/releases", json={
            "title": "API Sprint 44 Release",
            "version": "v4.4.0",
            "release_type": "minor"
        })
        self.assertEqual(res.status_code, 201)
        rel_id = res.json()["id"]

        res = self.client.post(f"/api/v2/releases/{rel_id}/stage", json={"stage": "completed"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["stage"], "completed")

    def test_api_catalog_and_requests(self):
        res = self.client.get("/api/v2/catalog")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertTrue(len(items) > 0)
        cat_id = items[0]["id"]

        res = self.client.post("/api/v2/requests", json={
            "catalog_item_id": cat_id,
            "requester_name": "Dana Scully",
            "requester_email": "dana.scully@enterprise.corp",
            "form_data": {"reason": "Routine testing"}
        })
        self.assertEqual(res.status_code, 201)
        req_id = res.json()["id"]

        res = self.client.put(f"/api/v2/requests/{req_id}/status", json={"status": "completed"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "completed")

    def test_api_knowledge_and_deflection(self):
        res = self.client.get("/api/v2/knowledge")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/v2/knowledge/search/deflection?title=Reset+password+and+mfa+token")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(len(res.json()) > 0)

        articles = self.client.get("/api/v2/knowledge").json()
        art_id = articles[0]["id"]
        res = self.client.post(f"/api/v2/knowledge/{art_id}/helpful")
        self.assertEqual(res.status_code, 200)

    def test_api_assets_contracts(self):
        res = self.client.get("/api/v2/assets/contracts/licenses")
        self.assertEqual(res.status_code, 200)
        lics = res.json()
        self.assertTrue(len(lics) > 0)
        lic_id = lics[0]["id"]

        res = self.client.post(f"/api/v2/assets/contracts/licenses/{lic_id}/allocate", json={"seats": 1})
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/api/v2/assets/contracts/licenses/{lic_id}/release", json={"seats": 1})
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/v2/assets/contracts/contracts")
        self.assertEqual(res.status_code, 200)

        res = self.client.get("/api/v2/assets/contracts/summary")
        self.assertEqual(res.status_code, 200)
        summary = res.json()
        self.assertIn("total_combined_itam_spend", summary)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFullITSMEngine))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFullITSMFastAPIRoutes))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
