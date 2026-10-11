"""OpenNow Incident Management V2 REST API Module
==================================================
ITIL-aligned Incident Lifecycle Management service with 3-tier taxonomy,
dynamic priority calculation matrix, automated business rules,
SLA clock engine with pause tracking, labor cost worklog accounting,
subtask management, and executive KPI analytics.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.database import db
from backend.config_engine import config_engine, config_router

router = APIRouter(prefix="/api/v2/incidents", tags=["Incident Management V2"])

# --- ITIL 3-Tier Taxonomy Tree ---

TAXONOMY_TREE = {
    "Hardware": {
        "Server": [
            "Memory Fault",
            "Disk Failure",
            "Power Supply Unit",
            "Motherboard / CPU",
            "Cooling & Fan Failure"
        ],
        "Network": [
            "Switch Port Down",
            "Router Crash",
            "Firewall Policy Drop",
            "Optic Transceiver Failure",
            "Physical Cable Damage"
        ],
        "Workstation": [
            "Laptop Battery Degraded",
            "Display / Monitor Glitch",
            "Keyboard / Trackpad Failure",
            "Docking Station",
            "Peripheral Device"
        ],
        "Storage": [
            "SAN Controller Fault",
            "NAS Volume Degraded",
            "Drive Array Rebuild Failure",
            "Fiber Channel Link Error"
        ]
    },
    "Software": {
        "Operating System": [
            "Kernel Panic / BSOD",
            "Patch / Update Failure",
            "OS Boot Loop",
            "Filesystem Corruption",
            "System Service Crash"
        ],
        "Enterprise Applications": [
            "SAP ERP Login Issue",
            "Salesforce API Sync Failure",
            "Office 365 Exchange Down",
            "Slack / Teams Disconnection",
            "Document Management Timeout"
        ],
        "Custom Services": [
            "API Gateway 500 Spike",
            "Microservice Connection Refused",
            "Auth Token Validation Failure",
            "Payment Processing Exception",
            "Kafka Consumer Lag Overflow"
        ]
    },
    "Database": {
        "Relational (Postgres/MySQL)": [
            "Deadlock Cascade",
            "Connection Pool Exhaustion",
            "Read Replica Replication Lag",
            "Slow Query Performance Spike",
            "Disk Space Full"
        ],
        "Enterprise (Oracle/MSSQL)": [
            "Tablespace Exceeded",
            "Blocking Session Contention",
            "Corrupted Index",
            "Archive Log Full",
            "Listener Down"
        ],
        "NoSQL & Cache (Redis/Mongo)": [
            "Redis OOM MaxMemory",
            "MongoDB Replica Set Failover",
            "Elasticsearch Red Cluster Status",
            "Cassandra Compaction Storm"
        ]
    },
    "Security": {
        "Access & Identity": [
            "Account Lockout Storm",
            "MFA Provider Outage",
            "Unauthorized Access Attempt",
            "SSO Certificate Expired",
            "Privilege Escalation Detected"
        ],
        "Threats & Incidents": [
            "Ransomware Suspicion",
            "Phishing Campaign Influx",
            "DDoS Traffic Surge",
            "Malware Alert on Host",
            "Data Exfiltration Alert"
        ]
    },
    "Cloud & Infrastructure": {
        "AWS / Multi-Cloud": [
            "EC2 Instance Health Check Failed",
            "S3 Bucket Permission Denied",
            "VPC Route Table Misconfiguration",
            "CloudWatch Alarm Triggered",
            "DirectConnect BGP Down"
        ],
        "Containers & Kubernetes": [
            "Pod CrashLoopBackOff",
            "OOMKilled Container",
            "Ingress Controller 502 / 504",
            "K8s Node NotReady",
            "PersistentVolumeClaim Mount Failure"
        ]
    }
}


# --- Lifecycle State Machine ---

ALLOWED_TRANSITIONS = {
    "New": ["Assigned", "In Progress", "Canceled"],
    "Assigned": ["In Progress", "On Hold", "Resolved", "Canceled"],
    "In Progress": ["On Hold", "Resolved", "Canceled"],
    "On Hold": ["In Progress", "Resolved", "Canceled"],
    "Resolved": ["Closed", "In Progress"],
    "Closed": [],
    "Canceled": []
}

CANONICAL_STATES = {
    "new": "New",
    "assigned": "Assigned",
    "in_progress": "In Progress",
    "in progress": "In Progress",
    "on_hold": "On Hold",
    "on hold": "On Hold",
    "resolved": "Resolved",
    "closed": "Closed",
    "canceled": "Canceled",
    "cancelled": "Canceled"
}

def canonicalize_state(state: str) -> str:
    cleaned = (state or "").strip().lower()
    return CANONICAL_STATES.get(cleaned, state.strip().title() if state else "New")


# --- Priority Calculation Matrix ---

def normalize_matrix_level(val: Any) -> int:
    """Extract integer 1, 2, or 3 from input like '1', '1 - High', 'High', 'Low'."""
    s = str(val or "").strip().lower()
    if s.startswith("1") or "high" in s or "critical" in s:
        return 1
    elif s.startswith("2") or "medium" in s or "moderate" in s:
        return 2
    elif s.startswith("3") or "low" in s:
        return 3
    return 3

def compute_priority_matrix(impact: Any, urgency: Any) -> Dict[str, Any]:
    """Calculates ITIL priority and SLA target hours dynamically from config_priority_matrix."""
    return config_engine.compute_priority(impact, urgency)


# --- Pydantic Request & Response Schemas ---

class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Brief summary of incident")
    description: Optional[str] = Field("", description="Detailed incident diagnosis or symptom")
    category: str = Field(..., description="Tier 1 category (e.g. Hardware, Software, Database, Security)")
    subcategory: Optional[str] = Field("", description="Tier 2 subcategory")
    item: Optional[str] = Field("", description="Tier 3 specific item")
    impact: str = Field(default="2 - Medium", description="Impact level: 1 - High, 2 - Medium, 3 - Low")
    urgency: str = Field(default="2 - Medium", description="Urgency level: 1 - High, 2 - Medium, 3 - Low")
    priority: Optional[str] = Field(None, description="Auto-calculated if omitted: P1, P2, P3, P4")
    caller: Optional[str] = Field("System", description="Initiator or requester email/name")
    assigned_to: Optional[str] = Field(None, description="Assigned engineer")
    assignment_group: Optional[str] = Field(None, description="Assigned team/queue")
    ci_id: Optional[str] = Field(None, description="Affected Configuration Item")
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary JSON metadata")

class IncidentTransitionRequest(BaseModel):
    target_state: str = Field(..., description="Target lifecycle state: Assigned, In Progress, On Hold, Resolved, Closed, Canceled")
    actor: Optional[str] = Field("system", description="User or service performing the transition")
    resolution_code: Optional[str] = Field(None, description="Required for Resolved: Solved (Permanently), Workaround, User Error, etc.")
    resolution_notes: Optional[str] = Field(None, description="Detailed explanation of how the incident was resolved")
    root_cause: Optional[str] = Field(None, description="Required for Resolved: Underlying defect or trigger")
    pause_reason: Optional[str] = Field(None, description="Required for On Hold: Awaiting Caller, Awaiting Vendor, Awaiting Change")
    notes: Optional[str] = Field(None, description="Optional transition log comment")

class WorklogCreate(BaseModel):
    technician: str = Field(..., min_length=1, description="Engineer or technician name")
    notes: str = Field(..., min_length=1, description="Work performed description")
    minutes_spent: float = Field(..., gt=0, description="Duration in minutes logged")
    hourly_rate: Optional[float] = Field(65.0, ge=0, description="Technician billing rate per hour")

class SubtaskCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Subtask title")
    description: Optional[str] = Field("", description="Subtask instructions")
    assigned_to: Optional[str] = Field("", description="Assigned assignee")
    status: Optional[str] = Field("open", description="Subtask status: open, in_progress, completed, cancelled")

class SubtaskUpdate(BaseModel):
    status: Optional[str] = Field(None, description="open, in_progress, completed, cancelled")
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None

class PriorityMatrixRequest(BaseModel):
    impact: str = Field(..., description="1 - High, 2 - Medium, 3 - Low or 1, 2, 3")
    urgency: str = Field(..., description="1 - High, 2 - Medium, 3 - Low or 1, 2, 3")


# --- Database Schema & Storage Manager ---

class IncidentDatabase:
    """Manages SQLite storage for the Incident Management V2 subsystem."""

    def __init__(self):
        self.init_schema()
        self.seed_defaults_if_empty()

    def init_schema(self) -> None:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS v2_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_number TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    item TEXT DEFAULT '',
                    impact TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'New',
                    caller TEXT DEFAULT 'System',
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
                CREATE TABLE IF NOT EXISTS v2_incident_worklogs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER NOT NULL,
                    technician TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    minutes_spent REAL NOT NULL,
                    hourly_rate REAL DEFAULT 65.0,
                    labor_cost REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES v2_incidents(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS v2_incident_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER NOT NULL,
                    task_number TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    assigned_to TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES v2_incidents(id) ON DELETE CASCADE
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
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES v2_incidents(id) ON DELETE CASCADE
                );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_v2_inc_state ON v2_incidents(state);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_v2_inc_priority ON v2_incidents(priority);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_v2_inc_cat ON v2_incidents(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_v2_inc_num ON v2_incidents(incident_number);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_v2_work_inc ON v2_incident_worklogs(incident_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_v2_task_inc ON v2_incident_tasks(incident_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_v2_hist_inc ON v2_incident_history(incident_id);")

    def generate_incident_number(self) -> str:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM v2_incidents ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            next_id = (row["id"] + 1) if row else 1
            return f"INC{next_id:07d}"

    def seed_defaults_if_empty(self) -> None:
        """Seed realistic enterprise incidents if database table is empty."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM v2_incidents")
            if cursor.fetchone()["cnt"] > 0:
                return

        now = datetime.datetime.utcnow()
        samples = [
            {
                "title": "PostgreSQL Aurora Primary connection pool exhausted and deadlock cascade",
                "description": "API Gateway returning 500 across checkout routes. Active DB connections at 1000/1000 limit.",
                "category": "Database",
                "subcategory": "Relational (Postgres/MySQL)",
                "item": "Connection Pool Exhaustion",
                "impact": "1 - High",
                "urgency": "1 - High",
                "priority": "P1",
                "state": "In Progress",
                "caller": "monitoring@opennow.io",
                "assigned_to": "alex.chen@opennow.io",
                "assignment_group": "Major Incident Response Team",
                "ci_id": "ci-db-postgres-primary",
                "created_at": (now - datetime.timedelta(minutes=45)).isoformat(),
                "sla_target_hours": 1.0,
                "is_fcr": 0,
                "worklogs": [
                    ("Alex Chen", "Terminated blocking idle-in-transaction sessions and raised pool limit", 30, 85.0)
                ],
                "subtasks": [
                    ("Inspect pg_stat_activity", "Analyze top blocking queries in Aurora", "alex.chen@opennow.io", "completed"),
                    ("Tune pgbouncer max_client_conn", "Deploy ConfigMap update to pgbouncer", "devops@opennow.io", "in_progress")
                ]
            },
            {
                "title": "Kong Ingress Pod CrashLoopBackOff after config update",
                "description": "Kong Ingress pods crashing immediately upon start with syntax error in ConfigMap.",
                "category": "Cloud & Infrastructure",
                "subcategory": "Containers & Kubernetes",
                "item": "Pod CrashLoopBackOff",
                "impact": "1 - High",
                "urgency": "2 - Medium",
                "priority": "P2",
                "state": "Assigned",
                "caller": "ci-bot@opennow.io",
                "assigned_to": "sam.k@opennow.io",
                "assignment_group": "Platform Engineering",
                "ci_id": "ci-kong-gateway",
                "created_at": (now - datetime.timedelta(minutes=90)).isoformat(),
                "sla_target_hours": 4.0,
                "is_fcr": 0,
                "worklogs": [
                    ("Sam K", "Reviewed git diff on helm values repo", 20, 75.0)
                ],
                "subtasks": [
                    ("Rollback helm release to revision 41", "Execute helm rollback kong-ingress", "sam.k@opennow.io", "open")
                ]
            },
            {
                "title": "Suspicious privilege escalation alert on bastion-01 host",
                "description": "CrowdStrike detected unauthorized sudo attempt by service account.",
                "category": "Security",
                "subcategory": "Threats & Incidents",
                "item": "Privilege Escalation Detected",
                "impact": "2 - Medium",
                "urgency": "1 - High",
                "priority": "P2",
                "state": "On Hold",
                "pause_reason": "Awaiting Evidence",
                "caller": "soc-alert@opennow.io",
                "assigned_to": "elena.r@opennow.io",
                "assignment_group": "Cybersecurity SOC",
                "ci_id": "ci-bastion-01",
                "created_at": (now - datetime.timedelta(hours=3)).isoformat(),
                "sla_target_hours": 4.0,
                "sla_paused_at": (now - datetime.timedelta(minutes=30)).isoformat(),
                "is_fcr": 0,
                "worklogs": [
                    ("Elena R", "Isolated host network interface and extracted memory dump", 45, 95.0)
                ],
                "subtasks": []
            },
            {
                "title": "SSL/TLS handshake failure on opennow.io domain",
                "description": "Browser certificate expired. Cert-manager ACME challenge failed with DNS timeout.",
                "category": "Security",
                "subcategory": "Access & Identity",
                "item": "SSO Certificate Expired",
                "impact": "1 - High",
                "urgency": "1 - High",
                "priority": "P1",
                "state": "Resolved",
                "caller": "executive@opennow.io",
                "assigned_to": "marcus.v@opennow.io",
                "assignment_group": "Cybersecurity SOC",
                "ci_id": "ci-opennow-edge",
                "resolution_code": "Solved (Permanently)",
                "root_cause": "ACME Cloudflare DNS API token had expired",
                "resolution_notes": "Rotated Cloudflare token in Vault and triggered cert-manager renewal.",
                "created_at": (now - datetime.timedelta(hours=5)).isoformat(),
                "resolved_at": (now - datetime.timedelta(hours=4, minutes=10)).isoformat(),
                "sla_target_hours": 1.0,
                "is_fcr": 1,
                "worklogs": [
                    ("Marcus V", "Regenerated API token and force-synced secret", 50, 80.0)
                ],
                "subtasks": [
                    ("Verify SSL expiry via OpenSSL CLI", "Verify cert validity is now 90 days", "marcus.v@opennow.io", "completed")
                ]
            }
        ]

        for s in samples:
            worklogs = s.pop("worklogs", [])
            subtasks = s.pop("subtasks", [])
            inc_id = self.insert_incident(s)
            for w in worklogs:
                self.add_worklog(inc_id, w[0], w[1], w[2], w[3])
            for t in subtasks:
                self.add_subtask(inc_id, t[0], t[1], t[2], t[3])

    def insert_incident(self, data: Dict[str, Any]) -> int:
        now_iso = datetime.datetime.utcnow().isoformat()
        created_at = data.get("created_at") or now_iso
        updated_at = data.get("updated_at") or now_iso
        sla_hours = float(data.get("sla_target_hours") or 4.0)

        # Calculate initial SLA due date if not provided
        created_dt = datetime.datetime.fromisoformat(created_at)
        if not data.get("sla_due_at"):
            due_dt, target_h = config_engine.calculate_sla_due_date(
                created_dt,
                priority=data.get("priority", "P3"),
                sla_hours_override=sla_hours
            )
            sla_due_at = due_dt.isoformat()
            sla_hours = target_h
        else:
            sla_due_at = data.get("sla_due_at")
        inc_number = data.get("incident_number") or self.generate_incident_number()

        with db.get_connection() as conn:
            cursor = conn.cursor()
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
                data.get("title", ""),
                data.get("description", ""),
                data.get("category", ""),
                data.get("subcategory", ""),
                data.get("item", ""),
                data.get("impact", "2 - Medium"),
                data.get("urgency", "2 - Medium"),
                data.get("priority", "P3"),
                data.get("state", "New"),
                data.get("caller", "System"),
                data.get("assigned_to", ""),
                data.get("assignment_group", ""),
                data.get("ci_id", ""),
                data.get("resolution_code", ""),
                data.get("resolution_notes", ""),
                data.get("root_cause", ""),
                data.get("pause_reason", ""),
                created_at,
                updated_at,
                data.get("resolved_at"),
                data.get("closed_at"),
                sla_hours,
                sla_due_at,
                int(data.get("sla_breached", 0)),
                float(data.get("sla_paused_total_seconds", 0.0)),
                data.get("sla_paused_at"),
                int(data.get("is_fcr", 0)),
                json.dumps(data.get("custom_fields", {}))
            ))
            inc_id = cursor.lastrowid

            # Initial audit history log
            cursor.execute("""
                INSERT INTO v2_incident_history (
                    incident_id, actor, action, from_state, to_state, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                inc_id,
                data.get("caller") or "System",
                "CREATE",
                "",
                data.get("state", "New"),
                f"Incident created with priority {data.get('priority', 'P3')}",
                now_iso
            ))
            return inc_id

    def get_incident(self, identifier: Union[int, str]) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if str(identifier).isdigit():
                cursor.execute("SELECT * FROM v2_incidents WHERE id = ?", (int(identifier),))
            else:
                cursor.execute("SELECT * FROM v2_incidents WHERE incident_number = ?", (str(identifier),))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def list_incidents(
        self,
        state: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        caller: Optional[str] = None,
        assigned_to: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM v2_incidents WHERE 1=1"
        params: List[Any] = []

        if state:
            can_state = canonicalize_state(state)
            query += " AND state = ?"
            params.append(can_state)

        if priority:
            query += " AND priority = ?"
            params.append(priority.strip().upper())

        if category:
            query += " AND category = ?"
            params.append(category.strip())

        if caller:
            query += " AND caller LIKE ?"
            params.append(f"%{caller.strip()}%")

        if assigned_to:
            query += " AND assigned_to LIKE ?"
            params.append(f"%{assigned_to.strip()}%")

        if search:
            query += " AND (title LIKE ? OR description LIKE ? OR incident_number LIKE ? OR caller LIKE ? OR assigned_to LIKE ?)"
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param, s_param, s_param])

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def add_worklog(
        self,
        incident_id: int,
        technician: str,
        notes: str,
        minutes_spent: float,
        hourly_rate: float = 65.0
    ) -> Dict[str, Any]:
        labor_cost = round((minutes_spent / 60.0) * hourly_rate, 2)
        now_iso = datetime.datetime.utcnow().isoformat()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO v2_incident_worklogs (
                    incident_id, technician, notes, minutes_spent, hourly_rate, labor_cost, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (incident_id, technician, notes, minutes_spent, hourly_rate, labor_cost, now_iso))
            worklog_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO v2_incident_history (
                    incident_id, actor, action, notes, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (incident_id, technician, "WORKLOG_ADDED", f"Logged {minutes_spent} mins (${labor_cost:.2f})", now_iso))

            # Query totals
            cursor.execute("""
                SELECT SUM(labor_cost) as total_cost, SUM(minutes_spent) as total_mins
                FROM v2_incident_worklogs WHERE incident_id = ?
            """, (incident_id,))
            totals = cursor.fetchone()
            total_cost = round(totals["total_cost"] or 0.0, 2)
            total_mins = round(totals["total_mins"] or 0.0, 1)

            return {
                "id": worklog_id,
                "incident_id": incident_id,
                "technician": technician,
                "notes": notes,
                "minutes_spent": minutes_spent,
                "hourly_rate": hourly_rate,
                "labor_cost": labor_cost,
                "created_at": now_iso,
                "total_labor_cost": total_cost,
                "total_minutes_logged": total_mins
            }

    def list_worklogs(self, incident_id: int) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM v2_incident_worklogs WHERE incident_id = ? ORDER BY id ASC
            """, (incident_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def add_subtask(
        self,
        incident_id: int,
        title: str,
        description: str = "",
        assigned_to: str = "",
        status: str = "open"
    ) -> Dict[str, Any]:
        now_iso = datetime.datetime.utcnow().isoformat()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM v2_incident_tasks WHERE incident_id = ?", (incident_id,))
            count = cursor.fetchone()["cnt"] + 1
            task_number = f"TSK{incident_id:05d}-{count:02d}"

            cursor.execute("""
                INSERT INTO v2_incident_tasks (
                    incident_id, task_number, title, description, assigned_to, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (incident_id, task_number, title, description, assigned_to, status, now_iso, now_iso))
            task_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO v2_incident_history (
                    incident_id, actor, action, notes, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (incident_id, assigned_to or "System", "SUBTASK_CREATED", f"Subtask {task_number} created: {title}", now_iso))

            return {
                "id": task_id,
                "incident_id": incident_id,
                "task_number": task_number,
                "title": title,
                "description": description,
                "assigned_to": assigned_to,
                "status": status,
                "created_at": now_iso,
                "updated_at": now_iso
            }

    def update_subtask(
        self,
        incident_id: int,
        task_id: int,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM v2_incident_tasks WHERE id = ? AND incident_id = ?", (task_id, incident_id))
            row = cursor.fetchone()
            if not row:
                return None

            now_iso = datetime.datetime.utcnow().isoformat()
            fields = []
            values = []
            for k in ["status", "title", "description", "assigned_to"]:
                if k in updates and updates[k] is not None:
                    fields.append(f"{k} = ?")
                    values.append(updates[k])
            fields.append("updated_at = ?")
            values.append(now_iso)

            values.extend([task_id, incident_id])
            cursor.execute(f"UPDATE v2_incident_tasks SET {', '.join(fields)} WHERE id = ? AND incident_id = ?", values)

            cursor.execute("""
                INSERT INTO v2_incident_history (
                    incident_id, actor, action, notes, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                incident_id,
                updates.get("assigned_to") or "System",
                "SUBTASK_UPDATED",
                f"Subtask {row['task_number']} updated: status={updates.get('status', row['status'])}",
                now_iso
            ))

            cursor.execute("SELECT * FROM v2_incident_tasks WHERE id = ?", (task_id,))
            return dict(cursor.fetchone())

    def list_subtasks(self, incident_id: int) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM v2_incident_tasks WHERE incident_id = ? ORDER BY id ASC", (incident_id,))
            return [dict(r) for r in cursor.fetchall()]

    def list_history(self, incident_id: int) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM v2_incident_history WHERE incident_id = ? ORDER BY id ASC", (incident_id,))
            return [dict(r) for r in cursor.fetchall()]

    def execute_transition(
        self,
        incident_id: int,
        req: IncidentTransitionRequest
    ) -> Dict[str, Any]:
        incident = self.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

        current_state = incident["state"]
        target_state = canonicalize_state(req.target_state)

        # 1. State machine validation
        valid_next_states = ALLOWED_TRANSITIONS.get(current_state, [])
        if target_state not in valid_next_states:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid lifecycle transition from '{current_state}' to '{target_state}'. Allowed next states: {valid_next_states}"
            )

        now_dt = datetime.datetime.utcnow()
        now_iso = now_dt.isoformat()

        # 2. Validation Guard: On Hold requires pause_reason
        if target_state == "On Hold":
            if not req.pause_reason or not req.pause_reason.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Transition to 'On Hold' requires a valid 'pause_reason' (e.g. 'Awaiting Caller', 'Awaiting Vendor', 'Awaiting Evidence')."
                )

        # 3. Validation Guard: Resolved requires resolution_code and root_cause, and checks active subtasks
        if target_state == "Resolved":
            if not req.resolution_code or not req.resolution_code.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Transition to 'Resolved' requires a valid 'resolution_code' (e.g. 'Solved (Permanently)', 'Workaround Provided')."
                )
            if not req.root_cause or not req.root_cause.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Transition to 'Resolved' requires a valid 'root_cause'."
                )

            # Subtask guard: check if any subtasks are open or in_progress
            subtasks = self.list_subtasks(incident_id)
            active_subtasks = [t for t in subtasks if t["status"] in ("open", "in_progress")]
            if active_subtasks:
                sub_nums = [t["task_number"] for t in active_subtasks]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot resolve incident with active subtasks ({', '.join(sub_nums)}). Complete or cancel all subtasks before resolving."
                )

        # 4. Handle SLA Clock Pause / Resume
        sla_paused_at = incident.get("sla_paused_at")
        sla_paused_total = float(incident.get("sla_paused_total_seconds") or 0.0)
        sla_due_at = incident.get("sla_due_at")

        if target_state == "On Hold":
            # Entering pause
            sla_paused_at = now_iso
        elif current_state == "On Hold" and target_state != "On Hold":
            # Resuming from pause
            if sla_paused_at:
                try:
                    pause_start = datetime.datetime.fromisoformat(sla_paused_at)
                    pause_delta = (now_dt - pause_start).total_seconds()
                    if pause_delta > 0:
                        sla_paused_total += pause_delta
                        # Push due date forward by the paused duration
                        if sla_due_at:
                            due_dt = datetime.datetime.fromisoformat(sla_due_at)
                            sla_due_at = (due_dt + datetime.timedelta(seconds=pause_delta)).isoformat()
                except Exception:
                    pass
                sla_paused_at = None

        # 5. Handle Resolved / Closed Timestamps & SLA Breach Check
        resolved_at = incident.get("resolved_at")
        closed_at = incident.get("closed_at")
        sla_breached = incident.get("sla_breached", 0)

        if target_state == "Resolved":
            resolved_at = now_iso
            # Check if resolved after SLA due date
            if sla_due_at:
                try:
                    due_dt = datetime.datetime.fromisoformat(sla_due_at)
                    if now_dt > due_dt:
                        sla_breached = 1
                except Exception:
                    pass

        elif target_state == "Closed":
            closed_at = now_iso
            if not resolved_at:
                resolved_at = now_iso

        elif target_state == "In Progress" and current_state == "Resolved":
            # Reopening incident
            resolved_at = None

        # 6. Persist Update
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE v2_incidents SET
                    state = ?,
                    resolution_code = COALESCE(?, resolution_code),
                    resolution_notes = COALESCE(?, resolution_notes),
                    root_cause = COALESCE(?, root_cause),
                    pause_reason = ?,
                    sla_paused_at = ?,
                    sla_paused_total_seconds = ?,
                    sla_due_at = ?,
                    sla_breached = ?,
                    resolved_at = ?,
                    closed_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                target_state,
                req.resolution_code if req.resolution_code else None,
                req.resolution_notes if req.resolution_notes else None,
                req.root_cause if req.root_cause else None,
                req.pause_reason if target_state == "On Hold" else "",
                sla_paused_at,
                sla_paused_total,
                sla_due_at,
                sla_breached,
                resolved_at,
                closed_at,
                now_iso,
                incident_id
            ))

            # Audit history record
            history_notes = req.notes or f"Transitioned from {current_state} to {target_state}"
            if req.resolution_code:
                history_notes += f" [Resolution: {req.resolution_code}]"
            if req.pause_reason:
                history_notes += f" [Pause Reason: {req.pause_reason}]"

            cursor.execute("""
                INSERT INTO v2_incident_history (
                    incident_id, actor, action, from_state, to_state, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                incident_id,
                req.actor or "system",
                "STATE_TRANSITION",
                current_state,
                target_state,
                history_notes,
                now_iso
            ))

        return self.get_incident_detail(incident_id)

    def get_incident_detail(self, identifier: Union[int, str]) -> Dict[str, Any]:
        incident = self.get_incident(identifier)
        if not incident:
            raise HTTPException(status_code=404, detail=f"Incident '{identifier}' not found")

        inc_id = incident["id"]
        worklogs = self.list_worklogs(inc_id)
        subtasks = self.list_subtasks(inc_id)
        history = self.list_history(inc_id)

        total_cost = round(sum(w["labor_cost"] for w in worklogs), 2)
        total_mins = round(sum(w["minutes_spent"] for w in worklogs), 1)

        sla_clock = self._compute_sla_clock(incident)

        incident["worklogs"] = worklogs
        incident["subtasks"] = subtasks
        incident["history"] = history
        incident["total_labor_cost"] = total_cost
        incident["total_minutes_logged"] = total_mins
        incident["sla_clock"] = sla_clock

        return incident

    def get_kpi_stats(self) -> Dict[str, Any]:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Total incidents count & counts by state
            cursor.execute("SELECT state, COUNT(*) as cnt FROM v2_incidents GROUP BY state")
            state_counts = {r["state"]: r["cnt"] for r in cursor.fetchall()}
            total_incidents = sum(state_counts.values())

            resolved_or_closed_cnt = state_counts.get("Resolved", 0) + state_counts.get("Closed", 0)

            # 2. First Contact Resolution (FCR) Rate
            cursor.execute("SELECT COUNT(*) as cnt FROM v2_incidents WHERE is_fcr = 1 AND state IN ('Resolved', 'Closed')")
            fcr_count = cursor.fetchone()["cnt"]
            fcr_rate = round((fcr_count / resolved_or_closed_cnt * 100.0), 1) if resolved_or_closed_cnt > 0 else 0.0

            # 3. Mean Time To Resolve (MTTR)
            cursor.execute("""
                SELECT created_at, resolved_at, sla_paused_total_seconds
                FROM v2_incidents
                WHERE resolved_at IS NOT NULL AND state IN ('Resolved', 'Closed')
            """)
            resolved_rows = cursor.fetchall()

            durations_minutes = []
            for r in resolved_rows:
                try:
                    c_dt = datetime.datetime.fromisoformat(r["created_at"])
                    res_dt = datetime.datetime.fromisoformat(r["resolved_at"])
                    paused_sec = float(r["sla_paused_total_seconds"] or 0.0)
                    active_sec = max(0.0, (res_dt - c_dt).total_seconds() - paused_sec)
                    durations_minutes.append(active_sec / 60.0)
                except Exception:
                    continue

            mttr_minutes = round(sum(durations_minutes) / len(durations_minutes), 1) if durations_minutes else 0.0
            mttr_hours = round(mttr_minutes / 60.0, 2)

            # 4. Total Labor Cost
            cursor.execute("SELECT SUM(labor_cost) as total_cost, SUM(minutes_spent) as total_mins FROM v2_incident_worklogs")
            cost_row = cursor.fetchone()
            total_labor_cost = round(cost_row["total_cost"] or 0.0, 2)
            total_labor_minutes = round(cost_row["total_mins"] or 0.0, 1)

            # 5. Active SLA Breaches
            now_iso = datetime.datetime.utcnow().isoformat()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM v2_incidents
                WHERE state NOT IN ('Resolved', 'Closed', 'Canceled')
                AND (sla_breached = 1 OR (sla_due_at IS NOT NULL AND sla_due_at < ?))
            """, (now_iso,))
            active_sla_breaches = cursor.fetchone()["cnt"]

            # 6. Priority breakdown
            cursor.execute("SELECT priority, COUNT(*) as cnt FROM v2_incidents GROUP BY priority")
            priority_counts = {r["priority"]: r["cnt"] for r in cursor.fetchall()}

            # 7. SLA Compliance Rate
            cursor.execute("""
                SELECT COUNT(*) as total_resolved,
                       SUM(CASE WHEN sla_breached = 0 THEN 1 ELSE 0 END) as met_sla
                FROM v2_incidents
                WHERE state IN ('Resolved', 'Closed')
            """)
            sla_row = cursor.fetchone()
            total_res = sla_row["total_resolved"] or 0
            met_sla = sla_row["met_sla"] or 0
            sla_compliance_rate = round((met_sla / total_res * 100.0), 1) if total_res > 0 else 100.0

            return {
                "total_incidents": total_incidents,
                "open_incidents": total_incidents - resolved_or_closed_cnt - state_counts.get("Canceled", 0),
                "resolved_incidents": state_counts.get("Resolved", 0),
                "closed_incidents": state_counts.get("Closed", 0),
                "state_breakdown": state_counts,
                "priority_breakdown": priority_counts,
                "fcr_rate": fcr_rate,
                "fcr_count": fcr_count,
                "mttr_minutes": mttr_minutes,
                "mttr_hours": mttr_hours,
                "active_sla_breaches": active_sla_breaches,
                "total_labor_cost": total_labor_cost,
                "total_labor_minutes": total_labor_minutes,
                "sla_compliance_rate": sla_compliance_rate
            }

    def _compute_sla_clock(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        target_hours = float(incident.get("sla_target_hours") or 4.0)
        target_seconds = target_hours * 3600.0
        now = datetime.datetime.utcnow()

        try:
            created_at = datetime.datetime.fromisoformat(incident["created_at"])
        except Exception:
            created_at = now

        paused_total = float(incident.get("sla_paused_total_seconds") or 0.0)
        is_paused = incident.get("state") == "On Hold" or bool(incident.get("sla_paused_at"))

        current_pause_delta = 0.0
        if incident.get("sla_paused_at"):
            try:
                pause_time = datetime.datetime.fromisoformat(incident["sla_paused_at"])
                current_pause_delta = max(0.0, (now - pause_time).total_seconds())
            except Exception:
                pass

        effective_paused_seconds = paused_total + current_pause_delta

        if incident.get("resolved_at"):
            try:
                end_time = datetime.datetime.fromisoformat(incident["resolved_at"])
            except Exception:
                end_time = now
        elif incident.get("closed_at"):
            try:
                end_time = datetime.datetime.fromisoformat(incident["closed_at"])
            except Exception:
                end_time = now
        else:
            end_time = now

        total_elapsed_seconds = max(0.0, (end_time - created_at).total_seconds())
        active_elapsed_seconds = max(0.0, total_elapsed_seconds - effective_paused_seconds)
        remaining_seconds = target_seconds - active_elapsed_seconds

        is_breached = bool(incident.get("sla_breached")) or (remaining_seconds < 0)
        pct_consumed = min(100.0, max(0.0, (active_elapsed_seconds / target_seconds) * 100.0)) if target_seconds > 0 else 100.0

        return {
            "target_hours": target_hours,
            "target_seconds": target_seconds,
            "active_elapsed_seconds": round(active_elapsed_seconds, 1),
            "paused_seconds": round(effective_paused_seconds, 1),
            "remaining_seconds": round(remaining_seconds, 1),
            "percentage_consumed": round(pct_consumed, 1),
            "is_paused": is_paused,
            "is_breached": is_breached,
            "sla_due_at": incident.get("sla_due_at")
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if isinstance(d.get("custom_fields"), str):
            try:
                d["custom_fields"] = json.loads(d["custom_fields"])
            except Exception:
                d["custom_fields"] = {}
        return d


# Global singleton instance
incident_db = IncidentDatabase()


# --- Business Rule Engine ---

def evaluate_business_rules(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Evaluates ITIL automated classification, routing, and escalation rules via config_engine."""
    return config_engine.evaluate_business_rules(payload)


# --- API Routes ---

# 1. Taxonomy Tree
@router.get("/taxonomy/tree", tags=["Incident Management V2"])
def get_taxonomy_tree() -> Dict[str, Any]:
    """Returns Category -> Subcategory -> Item 3-tier hierarchy dynamically from config tables."""
    return config_engine.get_taxonomy_tree()


# 2. Priority Matrix Calculator
@router.post("/priority-matrix/calculate", tags=["Incident Management V2"])
def calculate_priority_matrix(req: PriorityMatrixRequest) -> Dict[str, Any]:
    """Calculates ITIL priority and SLA target hours given Impact and Urgency."""
    return compute_priority_matrix(req.impact, req.urgency)


# 3. Executive KPI Stats
@router.get("/stats/kpi", tags=["Incident Management V2"])
def get_incident_kpis() -> Dict[str, Any]:
    """Computes FCR rate, MTTR, active SLA breaches, and labor cost aggregates."""
    return incident_db.get_kpi_stats()


# 4. List Incidents
@router.get("", tags=["Incident Management V2"])
def list_incidents(
    state: Optional[str] = Query(None, description="Filter by lifecycle state (New, Assigned, In Progress, On Hold, Resolved, Closed, Canceled)"),
    priority: Optional[str] = Query(None, description="Filter by priority (P1, P2, P3, P4)"),
    category: Optional[str] = Query(None, description="Filter by Tier 1 category"),
    caller: Optional[str] = Query(None, description="Filter by caller username or email"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned engineer"),
    search: Optional[str] = Query(None, description="Full-text query over title, description, incident_number, caller"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[Dict[str, Any]]:
    """Lists incidents with multi-facet ITIL filtering and full-text search."""
    return incident_db.list_incidents(
        state=state,
        priority=priority,
        category=category,
        caller=caller,
        assigned_to=assigned_to,
        search=search,
        limit=limit,
        offset=offset
    )


# 5. Create Incident
@router.post("", status_code=status.HTTP_201_CREATED, tags=["Incident Management V2"])
def create_incident(payload: IncidentCreate) -> Dict[str, Any]:
    """Creates a new incident with 3-tier categorization, auto-priority matrix, and business rules."""
    raw_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    evaluated_dict, applied_rules = evaluate_business_rules(raw_dict)

    inc_id = incident_db.insert_incident(evaluated_dict)
    detail = incident_db.get_incident_detail(inc_id)
    detail["business_rules_applied"] = applied_rules
    return detail


# 6. Allowed Transitions
@router.get("/{id}/allowed-transitions", tags=["Incident Management V2"])
def get_allowed_transitions(id: Union[int, str]) -> Dict[str, Any]:
    """Returns list of valid next states and their respective validation guards."""
    incident = incident_db.get_incident(id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    curr_state = incident["state"]
    allowed = ALLOWED_TRANSITIONS.get(curr_state, [])
    guards: Dict[str, List[str]] = {}
    if "On Hold" in allowed:
        guards["On Hold"] = ["pause_reason"]
    if "Resolved" in allowed:
        guards["Resolved"] = ["resolution_code", "root_cause", "no_active_subtasks"]

    return {
        "incident_id": incident["id"],
        "incident_number": incident["incident_number"],
        "current_state": curr_state,
        "allowed_transitions": allowed,
        "transition_guards": guards
    }


# 7. Transition Lifecycle State
@router.post("/{id}/transition", tags=["Incident Management V2"])
def transition_incident(id: Union[int, str], req: IncidentTransitionRequest) -> Dict[str, Any]:
    """Executes state transition with validation guards (pause_reason, resolution_code, root_cause)."""
    incident = incident_db.get_incident(id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    return incident_db.execute_transition(incident["id"], req)


# 8. Worklogs
@router.post("/{id}/worklogs", status_code=status.HTTP_201_CREATED, tags=["Incident Management V2"])
def add_worklog(id: Union[int, str], req: WorklogCreate) -> Dict[str, Any]:
    """Logs technician effort, updates labor costs, and returns total labor calculation."""
    incident = incident_db.get_incident(id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    rate = req.hourly_rate
    if rate is None or rate == 65.0:
        rate = config_engine.get_technician_rate(req.technician)

    return incident_db.add_worklog(
        incident_id=incident["id"],
        technician=req.technician,
        notes=req.notes,
        minutes_spent=req.minutes_spent,
        hourly_rate=rate
    )


@router.get("/{id}/worklogs", tags=["Incident Management V2"])
def list_worklogs(id: Union[int, str]) -> List[Dict[str, Any]]:
    """Lists technician worklogs and time spent for the incident."""
    incident = incident_db.get_incident(id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    return incident_db.list_worklogs(incident["id"])


# 9. Subtasks
@router.post("/{id}/tasks", status_code=status.HTTP_201_CREATED, tags=["Incident Management V2"])
def add_subtask(id: Union[int, str], req: SubtaskCreate) -> Dict[str, Any]:
    """Adds a granular subtask to the incident."""
    incident = incident_db.get_incident(id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    return incident_db.add_subtask(
        incident_id=incident["id"],
        title=req.title,
        description=req.description or "",
        assigned_to=req.assigned_to or "",
        status=req.status or "open"
    )


@router.patch("/{id}/tasks/{task_id}", tags=["Incident Management V2"])
def update_subtask(id: Union[int, str], task_id: int, req: SubtaskUpdate) -> Dict[str, Any]:
    """Updates subtask status or assignment."""
    incident = incident_db.get_incident(id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{id}' not found")

    updates = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
    updated = incident_db.update_subtask(incident["id"], task_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Subtask '{task_id}' not found for incident '{id}'")
    return updated


# 10. Get Incident Full Detail
@router.get("/{id}", tags=["Incident Management V2"])
def get_incident(id: Union[int, str]) -> Dict[str, Any]:
    """Returns full incident details with worklogs, subtasks, SLA clock, and audit history."""
    return incident_db.get_incident_detail(id)
