"""OpenNow Master Data Configuration Engine
===========================================
Enterprise configuration and master data engine inspired by Zoho ServiceDesk Plus,
Odoo, and SAP Service Management.

Manages:
1. 3-Tier Taxonomy (Categories, Subcategories, Items) with Active Toggles and CRUD
2. Priority Matrix Mapping Grid (Impact x Urgency -> Priority, Resolution SLA, Response SLA)
3. SLA Policies & Operational Schedules (24x7, Business Hours 09:00-18:00, Pausing status rules)
4. Resolution Codes & Root Cause Master Data
5. Technicians, Support Groups, and Dynamic Billing Rates ($/hr)
6. Dynamic Criteria-based Business Rules & Automated Routing Engine
7. REST API Endpoints under /api/v2/config
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.database import db

logger = logging.getLogger("opennow.config_engine")

config_router = APIRouter(prefix="/api/v2/config", tags=["Master Data Configuration"])


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    code: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = Field("", max_length=500)
    is_active: Optional[bool] = True

class CategoryUpdate(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class SubcategoryCreate(BaseModel):
    category_id: int
    name: str = Field(..., min_length=1, max_length=120)
    code: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = Field("", max_length=500)
    is_active: Optional[bool] = True

class SubcategoryUpdate(BaseModel):
    id: Optional[int] = None
    category_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ItemCreate(BaseModel):
    subcategory_id: int
    name: str = Field(..., min_length=1, max_length=120)
    code: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = Field("", max_length=500)
    is_active: Optional[bool] = True

class ItemUpdate(BaseModel):
    id: Optional[int] = None
    subcategory_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class PriorityMatrixUpdate(BaseModel):
    impact_level: int = Field(..., ge=1, le=3)
    urgency_level: int = Field(..., ge=1, le=3)
    priority_code: Optional[str] = Field(None, description="P1, P2, P3, P4")
    priority_label: Optional[str] = None
    resolution_sla_hours: Optional[float] = Field(None, gt=0)
    response_sla_hours: Optional[float] = Field(None, gt=0)

class ResolutionCodeCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=100)
    category: Optional[str] = Field("General", max_length=100)
    root_cause_options: Optional[List[str]] = Field(default_factory=list)
    description: Optional[str] = Field("", max_length=500)
    is_active: Optional[bool] = True

class ResolutionCodeUpdate(BaseModel):
    id: Optional[int] = None
    code: Optional[str] = Field(None, min_length=2, max_length=100)
    category: Optional[str] = None
    root_cause_options: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class SLAPolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field("", max_length=500)
    schedule_type: Optional[str] = Field("24x7", description="'24x7' or 'business_hours'")
    business_start_hour: Optional[int] = Field(9, ge=0, le=23)
    business_end_hour: Optional[int] = Field(18, ge=0, le=23)
    workdays: Optional[str] = Field("1,2,3,4,5", description="Comma-separated ISO weekday numbers 1-7")
    timezone: Optional[str] = Field("UTC")
    pause_states: Optional[List[str]] = Field(default_factory=lambda: ["On Hold"])
    pause_reasons: Optional[List[str]] = Field(default_factory=lambda: ["Awaiting Caller", "Awaiting Vendor", "Awaiting Change"])
    p1_resolution_hours: Optional[float] = Field(1.0, gt=0)
    p2_resolution_hours: Optional[float] = Field(4.0, gt=0)
    p3_resolution_hours: Optional[float] = Field(8.0, gt=0)
    p4_resolution_hours: Optional[float] = Field(24.0, gt=0)
    p1_response_hours: Optional[float] = Field(0.25, gt=0)
    p2_response_hours: Optional[float] = Field(1.0, gt=0)
    p3_response_hours: Optional[float] = Field(2.0, gt=0)
    p4_response_hours: Optional[float] = Field(4.0, gt=0)
    is_default: Optional[bool] = False
    is_active: Optional[bool] = True

class SLAPolicyUpdate(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    schedule_type: Optional[str] = None
    business_start_hour: Optional[int] = None
    business_end_hour: Optional[int] = None
    workdays: Optional[str] = None
    timezone: Optional[str] = None
    pause_states: Optional[List[str]] = None
    pause_reasons: Optional[List[str]] = None
    p1_resolution_hours: Optional[float] = None
    p2_resolution_hours: Optional[float] = None
    p3_resolution_hours: Optional[float] = None
    p4_resolution_hours: Optional[float] = None
    p1_response_hours: Optional[float] = None
    p2_response_hours: Optional[float] = None
    p3_response_hours: Optional[float] = None
    p4_response_hours: Optional[float] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

class TechnicianCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., min_length=5, max_length=150)
    hourly_rate: Optional[float] = Field(65.0, ge=0)
    support_group: Optional[str] = Field("Service Desk", max_length=120)
    role: Optional[str] = Field("Technician", max_length=100)
    is_active: Optional[bool] = True

class TechnicianUpdate(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    hourly_rate: Optional[float] = None
    support_group: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class BusinessRuleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field("", max_length=500)
    order_num: Optional[int] = Field(10, ge=1)
    is_active: Optional[bool] = True
    criteria: Union[Dict[str, Any], List[Dict[str, Any]]]
    actions: Dict[str, Any]

class BusinessRuleUpdate(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    order_num: Optional[int] = None
    is_active: Optional[bool] = None
    criteria: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    actions: Optional[Dict[str, Any]] = None


# ============================================================================
# MASTER DATA CONFIGURATION ENGINE CLASS
# ============================================================================

class ConfigEngine:
    """Enterprise Master Data & Configuration Management Engine.
    Handles taxonomy, SLA policies, priority matrices, resolution codes,
    technicians, and criteria-driven business rules.
    """

    def __init__(self):
        self.init_schema()
        self.seed_defaults_if_empty()

    def init_schema(self) -> None:
        """Creates master data configuration tables if they do not exist."""
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Categories
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    code TEXT UNIQUE,
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Subcategories
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_subcategories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    code TEXT,
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (category_id) REFERENCES config_categories(id) ON DELETE CASCADE,
                    UNIQUE(category_id, name)
                );
            """)

            # 3. Items
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subcategory_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    code TEXT,
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (subcategory_id) REFERENCES config_subcategories(id) ON DELETE CASCADE,
                    UNIQUE(subcategory_id, name)
                );
            """)

            # 4. Priority Matrix (Impact x Urgency)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_priority_matrix (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    impact_level INTEGER NOT NULL,
                    urgency_level INTEGER NOT NULL,
                    priority_code TEXT NOT NULL,
                    priority_label TEXT NOT NULL,
                    resolution_sla_hours REAL NOT NULL,
                    response_sla_hours REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(impact_level, urgency_level)
                );
            """)

            # 5. SLA Policies & Schedules
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_sla_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT DEFAULT '',
                    schedule_type TEXT NOT NULL DEFAULT '24x7',
                    business_start_hour INTEGER DEFAULT 9,
                    business_end_hour INTEGER DEFAULT 18,
                    workdays TEXT DEFAULT '1,2,3,4,5',
                    timezone TEXT DEFAULT 'UTC',
                    pause_states TEXT DEFAULT '["On Hold"]',
                    pause_reasons TEXT DEFAULT '["Awaiting Caller","Awaiting Vendor","Awaiting Change"]',
                    p1_resolution_hours REAL DEFAULT 1.0,
                    p2_resolution_hours REAL DEFAULT 4.0,
                    p3_resolution_hours REAL DEFAULT 8.0,
                    p4_resolution_hours REAL DEFAULT 24.0,
                    p1_response_hours REAL DEFAULT 0.25,
                    p2_response_hours REAL DEFAULT 1.0,
                    p3_response_hours REAL DEFAULT 2.0,
                    p4_response_hours REAL DEFAULT 4.0,
                    is_default INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 6. Resolution Codes & Root Cause Master Data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_resolution_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    category TEXT DEFAULT 'General',
                    root_cause_options TEXT DEFAULT '[]',
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 7. Technicians, Billing Rates & Support Groups
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_technicians (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    hourly_rate REAL DEFAULT 65.0,
                    support_group TEXT NOT NULL DEFAULT 'Service Desk',
                    role TEXT DEFAULT 'Technician',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 8. Business Rules
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_business_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    order_num INTEGER DEFAULT 10,
                    is_active INTEGER DEFAULT 1,
                    criteria TEXT NOT NULL,
                    actions TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # Fast index creation
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subcat_cat ON config_subcategories(category_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_subcat ON config_items(subcategory_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_matrix_lvl ON config_priority_matrix(impact_level, urgency_level);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tech_email ON config_technicians(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_ord ON config_business_rules(order_num);")

    def seed_defaults_if_empty(self) -> None:
        """Populates comprehensive master data if tables are empty."""
        now = datetime.datetime.utcnow().isoformat()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Seed Categories, Subcategories, Items
            cursor.execute("SELECT COUNT(*) as cnt FROM config_categories")
            if cursor.fetchone()["cnt"] == 0:
                taxonomy_seed = {
                    "Hardware": {
                        "Server": ["Memory Fault", "Disk Failure", "Power Supply Unit", "Motherboard / CPU", "Cooling & Fan Failure"],
                        "Network": ["Switch Port Down", "Router Crash", "Firewall Policy Drop", "Optic Transceiver Failure", "Physical Cable Damage"],
                        "Workstation": ["Laptop Battery Degraded", "Display / Monitor Glitch", "Keyboard / Trackpad Failure", "Docking Station", "Peripheral Device"],
                        "Storage": ["SAN Controller Fault", "NAS Volume Degraded", "Drive Array Rebuild Failure", "Fiber Channel Link Error"]
                    },
                    "Software": {
                        "Operating System": ["Kernel Panic / BSOD", "Patch / Update Failure", "OS Boot Loop", "Filesystem Corruption", "System Service Crash"],
                        "Enterprise Applications": ["SAP ERP Login Issue", "Salesforce API Sync Failure", "Office 365 Exchange Down", "Slack / Teams Disconnection", "Document Management Timeout"],
                        "Custom Services": ["API Gateway 500 Spike", "Microservice Connection Refused", "Auth Token Validation Failure", "Payment Processing Exception", "Kafka Consumer Lag Overflow"]
                    },
                    "Database": {
                        "Relational (Postgres/MySQL)": ["Deadlock Cascade", "Connection Pool Exhaustion", "Read Replica Replication Lag", "Slow Query Performance Spike", "Disk Space Full"],
                        "Enterprise (Oracle/MSSQL)": ["Tablespace Exceeded", "Blocking Session Contention", "Corrupted Index", "Archive Log Full", "Listener Down"],
                        "NoSQL & Cache (Redis/Mongo)": ["Redis OOM MaxMemory", "MongoDB Replica Set Failover", "Elasticsearch Red Cluster Status", "Cassandra Compaction Storm"]
                    },
                    "Security": {
                        "Access & Identity": ["Account Lockout Storm", "MFA Provider Outage", "Unauthorized Access Attempt", "SSO Certificate Expired", "Privilege Escalation Detected"],
                        "Threats & Incidents": ["Ransomware Suspicion", "Phishing Campaign Influx", "DDoS Traffic Surge", "Malware Alert on Host", "Data Exfiltration Alert"]
                    },
                    "Cloud & Infrastructure": {
                        "AWS / Multi-Cloud": ["EC2 Instance Health Check Failed", "S3 Bucket Permission Denied", "VPC Route Table Misconfiguration", "CloudWatch Alarm Triggered", "DirectConnect BGP Down"],
                        "Containers & Kubernetes": ["Pod CrashLoopBackOff", "OOMKilled Container", "Ingress Controller 502 / 504", "K8s Node NotReady", "PersistentVolumeClaim Mount Failure"]
                    }
                }
                for cat_name, subcats in taxonomy_seed.items():
                    cursor.execute("""
                        INSERT INTO config_categories (name, code, description, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, 1, ?, ?)
                    """, (cat_name, cat_name.upper().replace(" ", "_").replace("&", "AND"), f"{cat_name} ITIL Category", now, now))
                    cat_id = cursor.lastrowid
                    for subcat_name, items in subcats.items():
                        cursor.execute("""
                            INSERT INTO config_subcategories (category_id, name, code, description, is_active, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 1, ?, ?)
                        """, (cat_id, subcat_name, subcat_name.upper().replace(" ", "_").replace("/", "_"), f"{subcat_name} Subcategory", now, now))
                        subcat_id = cursor.lastrowid
                        for item_name in items:
                            cursor.execute("""
                                INSERT INTO config_items (subcategory_id, name, code, description, is_active, created_at, updated_at)
                                VALUES (?, ?, ?, ?, 1, ?, ?)
                            """, (subcat_id, item_name, item_name.upper().replace(" ", "_").replace("/", "_"), f"{item_name} Configuration Item", now, now))

            # Seed Priority Matrix
            cursor.execute("SELECT COUNT(*) as cnt FROM config_priority_matrix")
            if cursor.fetchone()["cnt"] == 0:
                matrix_seeds = [
                    (1, 1, "P1", "P1 - Critical", 1.0, 0.25),
                    (1, 2, "P2", "P2 - High", 4.0, 0.5),
                    (1, 3, "P3", "P3 - Moderate", 8.0, 1.0),
                    (2, 1, "P2", "P2 - High", 4.0, 0.5),
                    (2, 2, "P3", "P3 - Moderate", 8.0, 1.0),
                    (2, 3, "P4", "P4 - Low", 24.0, 2.0),
                    (3, 1, "P3", "P3 - Moderate", 8.0, 1.0),
                    (3, 2, "P4", "P4 - Low", 24.0, 2.0),
                    (3, 3, "P4", "P4 - Low", 24.0, 4.0),
                ]
                for imp, urg, code, label, res_sla, resp_sla in matrix_seeds:
                    cursor.execute("""
                        INSERT INTO config_priority_matrix (
                            impact_level, urgency_level, priority_code, priority_label,
                            resolution_sla_hours, response_sla_hours, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (imp, urg, code, label, res_sla, resp_sla, now, now))

            # Seed SLA Policies
            cursor.execute("SELECT COUNT(*) as cnt FROM config_sla_policies")
            if cursor.fetchone()["cnt"] == 0:
                cursor.execute("""
                    INSERT INTO config_sla_policies (
                        name, description, schedule_type, business_start_hour, business_end_hour,
                        workdays, timezone, pause_states, pause_reasons,
                        p1_resolution_hours, p2_resolution_hours, p3_resolution_hours, p4_resolution_hours,
                        p1_response_hours, p2_response_hours, p3_response_hours, p4_response_hours,
                        is_default, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "Standard 24x7 SLA Policy",
                    "Continuous round-the-clock enterprise SLA policy with automatic On Hold clock pause.",
                    "24x7", 9, 18, "1,2,3,4,5,6,7", "UTC",
                    json.dumps(["On Hold"]),
                    json.dumps(["Awaiting Caller", "Awaiting Vendor", "Awaiting Change", "Awaiting Evidence"]),
                    1.0, 4.0, 8.0, 24.0,
                    0.25, 1.0, 2.0, 4.0,
                    1, 1, now, now
                ))

                cursor.execute("""
                    INSERT INTO config_sla_policies (
                        name, description, schedule_type, business_start_hour, business_end_hour,
                        workdays, timezone, pause_states, pause_reasons,
                        p1_resolution_hours, p2_resolution_hours, p3_resolution_hours, p4_resolution_hours,
                        p1_response_hours, p2_response_hours, p3_response_hours, p4_response_hours,
                        is_default, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "Business Hours SLA (09:00-18:00 Mon-Fri)",
                    "Standard weekday operational schedule pausing SLA outside 09:00 to 18:00 window.",
                    "business_hours", 9, 18, "1,2,3,4,5", "UTC",
                    json.dumps(["On Hold"]),
                    json.dumps(["Awaiting Caller", "Awaiting Vendor"]),
                    2.0, 8.0, 16.0, 40.0,
                    0.5, 2.0, 4.0, 8.0,
                    0, 1, now, now
                ))

            # Seed Resolution Codes & Root Cause Master Data
            cursor.execute("SELECT COUNT(*) as cnt FROM config_resolution_codes")
            if cursor.fetchone()["cnt"] == 0:
                res_seeds = [
                    ("Solved (Permanently)", "Resolution", ["Code Defect Fixed", "Hardware Replaced", "Config Changed", "Permission Corrected", "ACME Cloudflare DNS API token had expired"]),
                    ("Workaround Provided", "Workaround", ["Temporary Route Added", "Service Restarted", "Failover to Standby", "Bypassed Cloudflare"]),
                    ("User Error", "Training", ["Incorrect Credentials", "Workflow Not Followed", "User Confusion"]),
                    ("Software Bug", "Development", ["Null Pointer Dereference", "Deadlock Cascade", "Memory Leak"]),
                    ("Hardware Failure", "Infrastructure", ["Disk Controller Fault", "Optic Transceiver Failure", "Power Supply Unit Short"]),
                    ("Configuration Rollback", "Operations", ["Failed Deployment", "Corrupted Schema Change", "Env Var Missing"]),
                    ("Vendor Escalation", "Third Party", ["ISP Fiber Cut", "Cloud Provider Region Outage", "SaaS Upstream Downtime"])
                ]
                for code, cat, causes in res_seeds:
                    cursor.execute("""
                        INSERT INTO config_resolution_codes (code, category, root_cause_options, description, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 1, ?, ?)
                    """, (code, cat, json.dumps(causes), f"Resolution code for {code}", now, now))

            # Seed Technicians, Billing Rates & Support Groups
            cursor.execute("SELECT COUNT(*) as cnt FROM config_technicians")
            if cursor.fetchone()["cnt"] == 0:
                tech_seeds = [
                    ("Marcus V", "marcus.v@opennow.io", 80.0, "Cybersecurity SOC", "Senior Security Engineer"),
                    ("Elena R", "elena.r@opennow.io", 95.0, "Data Center Infrastructure", "Principal Systems Engineer"),
                    ("Sarah Chen", "sarah.c@opennow.io", 110.0, "Database Engineering", "Lead Database Administrator"),
                    ("Alex Kim", "alex.k@opennow.io", 90.0, "Platform & Cloud Ops", "Cloud SRE"),
                    ("Jordan Smith", "jordan.s@opennow.io", 65.0, "Service Desk", "Service Desk Technician")
                ]
                for name, email, rate, group, role in tech_seeds:
                    cursor.execute("""
                        INSERT INTO config_technicians (name, email, hourly_rate, support_group, role, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """, (name, email, rate, group, role, now, now))

            # Seed Business Rules
            cursor.execute("SELECT COUNT(*) as cnt FROM config_business_rules")
            if cursor.fetchone()["cnt"] == 0:
                rule_seeds = [
                    (
                        "VIP Caller Auto-Escalation",
                        "Automatically escalates priority by one tier if caller matches VIP executive keywords",
                        10,
                        {"field": "caller", "operator": "contains_any", "values": ["vip", "ceo", "cto", "cio", "cfo", "director", "executive", "vp"]},
                        {"priority_bump": 1}
                    ),
                    (
                        "P1 Major Incident Auto-Routing",
                        "Routes any P1 Critical incident immediately to the Major Incident Response Team",
                        20,
                        {"field": "priority", "operator": "equals", "value": "P1"},
                        {"assignment_group": "Major Incident Response Team"}
                    ),
                    (
                        "Security Incident SOC Routing",
                        "Automatically assigns Security taxonomy incidents to Cybersecurity SOC queue",
                        30,
                        {"field": "category", "operator": "contains", "value": "Security"},
                        {"assignment_group": "Cybersecurity SOC"}
                    ),
                    (
                        "Database Incident Routing",
                        "Automatically routes Database category incidents to Database Engineering queue",
                        40,
                        {"field": "category", "operator": "contains", "value": "Database"},
                        {"assignment_group": "Database Engineering"}
                    ),
                    (
                        "Platform & Cloud Operations Routing",
                        "Directs Cloud, Containers, and Kubernetes incidents to Platform & Cloud Ops",
                        50,
                        {"field": "category", "operator": "contains_any", "values": ["Cloud", "Kubernetes", "Infrastructure"]},
                        {"assignment_group": "Platform & Cloud Ops"}
                    ),
                    (
                        "Hardware Data Center Routing",
                        "Directs physical hardware tickets to Data Center Infrastructure team",
                        60,
                        {"field": "category", "operator": "contains", "value": "Hardware"},
                        {"assignment_group": "Data Center Infrastructure"}
                    )
                ]
                for name, desc, order_num, criteria, actions in rule_seeds:
                    cursor.execute("""
                        INSERT INTO config_business_rules (name, description, order_num, is_active, criteria, actions, created_at, updated_at)
                        VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                    """, (name, desc, order_num, json.dumps(criteria), json.dumps(actions), now, now))

    # ------------------------------------------------------------------------
    # 1. TAXONOMY (Categories, Subcategories, Items)
    # ------------------------------------------------------------------------

    def list_categories(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            q = "SELECT * FROM config_categories"
            if not include_inactive:
                q += " WHERE is_active = 1"
            q += " ORDER BY name ASC"
            cursor.execute(q)
            return [dict(r) for r in cursor.fetchall()]

    def get_category(self, id_or_name: Union[int, str]) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if str(id_or_name).isdigit():
                cursor.execute("SELECT * FROM config_categories WHERE id = ?", (int(id_or_name),))
            else:
                cursor.execute("SELECT * FROM config_categories WHERE name = ?", (str(id_or_name),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_category(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.datetime.utcnow().isoformat()
        name = data["name"].strip()
        code = data.get("code") or name.upper().replace(" ", "_").replace("&", "AND")
        desc = data.get("description", "")
        is_active = 1 if data.get("is_active", True) else 0

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO config_categories (name, code, description, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, code, desc, is_active, now, now))
            cat_id = cursor.lastrowid
        return self.get_category(cat_id)

    def update_category(self, category_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_category(category_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Category '{category_id}' not found")

        now = datetime.datetime.utcnow().isoformat()
        name = data.get("name", existing["name"]).strip()
        code = data.get("code", existing["code"])
        desc = data.get("description", existing["description"])
        is_active = existing["is_active"] if data.get("is_active") is None else (1 if data.get("is_active") else 0)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE config_categories SET
                    name = ?, code = ?, description = ?, is_active = ?, updated_at = ?
                WHERE id = ?
            """, (name, code, desc, is_active, now, category_id))
        return self.get_category(category_id)

    def delete_category(self, category_id: int) -> bool:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_categories WHERE id = ?", (category_id,))
            return cursor.rowcount > 0

    def toggle_category_active(self, category_id: int, is_active: Optional[bool] = None) -> Dict[str, Any]:
        existing = self.get_category(category_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Category '{category_id}' not found")
        new_active = (1 if is_active else 0) if is_active is not None else (0 if existing["is_active"] == 1 else 1)
        return self.update_category(category_id, {"is_active": bool(new_active)})

    # Subcategories CRUD
    def list_subcategories(self, category_id: Optional[int] = None, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT s.*, c.name as category_name FROM config_subcategories s JOIN config_categories c ON s.category_id = c.id WHERE 1=1"
            params: List[Any] = []
            if category_id:
                query += " AND s.category_id = ?"
                params.append(category_id)
            if not include_inactive:
                query += " AND s.is_active = 1 AND c.is_active = 1"
            query += " ORDER BY s.name ASC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_subcategory(self, subcategory_id: int) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT s.*, c.name as category_name FROM config_subcategories s JOIN config_categories c ON s.category_id = c.id WHERE s.id = ?", (subcategory_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_subcategory(self, data: Dict[str, Any]) -> Dict[str, Any]:
        cat_id = data["category_id"]
        cat = self.get_category(cat_id)
        if not cat:
            raise HTTPException(status_code=400, detail=f"Referenced category_id '{cat_id}' does not exist")
        now = datetime.datetime.utcnow().isoformat()
        name = data["name"].strip()
        code = data.get("code") or name.upper().replace(" ", "_")
        desc = data.get("description", "")
        is_active = 1 if data.get("is_active", True) else 0

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO config_subcategories (category_id, name, code, description, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cat_id, name, code, desc, is_active, now, now))
            sub_id = cursor.lastrowid
        return self.get_subcategory(sub_id)

    def update_subcategory(self, subcategory_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_subcategory(subcategory_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Subcategory '{subcategory_id}' not found")
        now = datetime.datetime.utcnow().isoformat()
        cat_id = data.get("category_id", existing["category_id"])
        name = data.get("name", existing["name"]).strip()
        code = data.get("code", existing["code"])
        desc = data.get("description", existing["description"])
        is_active = existing["is_active"] if data.get("is_active") is None else (1 if data.get("is_active") else 0)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE config_subcategories SET
                    category_id = ?, name = ?, code = ?, description = ?, is_active = ?, updated_at = ?
                WHERE id = ?
            """, (cat_id, name, code, desc, is_active, now, subcategory_id))
        return self.get_subcategory(subcategory_id)

    def delete_subcategory(self, subcategory_id: int) -> bool:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_subcategories WHERE id = ?", (subcategory_id,))
            return cursor.rowcount > 0

    def toggle_subcategory_active(self, subcategory_id: int, is_active: Optional[bool] = None) -> Dict[str, Any]:
        existing = self.get_subcategory(subcategory_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Subcategory '{subcategory_id}' not found")
        new_active = (1 if is_active else 0) if is_active is not None else (0 if existing["is_active"] == 1 else 1)
        return self.update_subcategory(subcategory_id, {"is_active": bool(new_active)})

    # Items CRUD
    def list_items(self, subcategory_id: Optional[int] = None, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT i.*, s.name as subcategory_name, c.name as category_name
                FROM config_items i
                JOIN config_subcategories s ON i.subcategory_id = s.id
                JOIN config_categories c ON s.category_id = c.id
                WHERE 1=1
            """
            params: List[Any] = []
            if subcategory_id:
                query += " AND i.subcategory_id = ?"
                params.append(subcategory_id)
            if not include_inactive:
                query += " AND i.is_active = 1 AND s.is_active = 1 AND c.is_active = 1"
            query += " ORDER BY i.name ASC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.*, s.name as subcategory_name, c.name as category_name
                FROM config_items i
                JOIN config_subcategories s ON i.subcategory_id = s.id
                JOIN config_categories c ON s.category_id = c.id
                WHERE i.id = ?
            """, (item_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        sub_id = data["subcategory_id"]
        sub = self.get_subcategory(sub_id)
        if not sub:
            raise HTTPException(status_code=400, detail=f"Referenced subcategory_id '{sub_id}' does not exist")
        now = datetime.datetime.utcnow().isoformat()
        name = data["name"].strip()
        code = data.get("code") or name.upper().replace(" ", "_")
        desc = data.get("description", "")
        is_active = 1 if data.get("is_active", True) else 0

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO config_items (subcategory_id, name, code, description, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sub_id, name, code, desc, is_active, now, now))
            item_id = cursor.lastrowid
        return self.get_item(item_id)

    def update_item(self, item_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_item(item_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
        now = datetime.datetime.utcnow().isoformat()
        sub_id = data.get("subcategory_id", existing["subcategory_id"])
        name = data.get("name", existing["name"]).strip()
        code = data.get("code", existing["code"])
        desc = data.get("description", existing["description"])
        is_active = existing["is_active"] if data.get("is_active") is None else (1 if data.get("is_active") else 0)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE config_items SET
                    subcategory_id = ?, name = ?, code = ?, description = ?, is_active = ?, updated_at = ?
                WHERE id = ?
            """, (sub_id, name, code, desc, is_active, now, item_id))
        return self.get_item(item_id)

    def delete_item(self, item_id: int) -> bool:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_items WHERE id = ?", (item_id,))
            return cursor.rowcount > 0

    def toggle_item_active(self, item_id: int, is_active: Optional[bool] = None) -> Dict[str, Any]:
        existing = self.get_item(item_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
        new_active = (1 if is_active else 0) if is_active is not None else (0 if existing["is_active"] == 1 else 1)
        return self.update_item(item_id, {"is_active": bool(new_active)})

    def get_taxonomy_tree(self, include_inactive: bool = False) -> Dict[str, Any]:
        """Constructs full dynamic 3-tier taxonomy tree reflecting active database tables."""
        categories = self.list_categories(include_inactive=include_inactive)
        subcategories = self.list_subcategories(include_inactive=include_inactive)
        items = self.list_items(include_inactive=include_inactive)

        # Build lookup maps
        items_by_sub: Dict[int, List[str]] = {}
        for it in items:
            items_by_sub.setdefault(it["subcategory_id"], []).append(it["name"])

        subcats_by_cat: Dict[int, List[Dict[str, Any]]] = {}
        for sub in subcategories:
            subcats_by_cat.setdefault(sub["category_id"], []).append({
                "id": sub["id"],
                "name": sub["name"],
                "code": sub["code"],
                "is_active": bool(sub["is_active"]),
                "items": items_by_sub.get(sub["id"], [])
            })

        categories_list = []
        taxonomy_dict: Dict[str, Dict[str, List[str]]] = {}

        for cat in categories:
            cat_subs = subcats_by_cat.get(cat["id"], [])
            sub_dict: Dict[str, List[str]] = {}
            for s in cat_subs:
                sub_dict[s["name"]] = s["items"]

            taxonomy_dict[cat["name"]] = sub_dict
            categories_list.append({
                "id": cat["id"],
                "name": cat["name"],
                "code": cat["code"],
                "is_active": bool(cat["is_active"]),
                "subcategories": cat_subs
            })

        return {
            "taxonomy": taxonomy_dict,
            "categories": categories_list,
            "category_names": [c["name"] for c in categories_list]
        }

    # ------------------------------------------------------------------------
    # 2. PRIORITY MATRIX (Impact x Urgency -> Priority & SLAs)
    # ------------------------------------------------------------------------

    def list_priority_matrix(self) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM config_priority_matrix ORDER BY impact_level ASC, urgency_level ASC")
            return [dict(r) for r in cursor.fetchall()]

    def update_priority_matrix_entry(
        self,
        impact_level: int,
        urgency_level: int,
        priority_code: Optional[str] = None,
        priority_label: Optional[str] = None,
        resolution_sla_hours: Optional[float] = None,
        response_sla_hours: Optional[float] = None,
    ) -> Dict[str, Any]:
        now = datetime.datetime.utcnow().isoformat()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM config_priority_matrix WHERE impact_level = ? AND urgency_level = ?", (impact_level, urgency_level))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Matrix cell for ({impact_level}, {urgency_level}) not found")
            existing = dict(row)

            new_code = (priority_code or existing["priority_code"]).strip().upper()
            new_label = priority_label or existing["priority_label"] or f"{new_code} Priority"
            new_res_sla = float(resolution_sla_hours) if resolution_sla_hours is not None else existing["resolution_sla_hours"]
            new_resp_sla = float(response_sla_hours) if response_sla_hours is not None else existing["response_sla_hours"]

            cursor.execute("""
                UPDATE config_priority_matrix SET
                    priority_code = ?, priority_label = ?, resolution_sla_hours = ?, response_sla_hours = ?, updated_at = ?
                WHERE impact_level = ? AND urgency_level = ?
            """, (new_code, new_label, new_res_sla, new_resp_sla, now, impact_level, urgency_level))

            cursor.execute("SELECT * FROM config_priority_matrix WHERE impact_level = ? AND urgency_level = ?", (impact_level, urgency_level))
            return dict(cursor.fetchone())

    def compute_priority(self, impact: Any, urgency: Any) -> Dict[str, Any]:
        """Calculates dynamic priority and SLA hours from database config_priority_matrix table."""
        i_lvl = self._normalize_level(impact)
        u_lvl = self._normalize_level(urgency)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM config_priority_matrix
                WHERE impact_level = ? AND urgency_level = ?
            """, (i_lvl, u_lvl))
            row = cursor.fetchone()

        level_labels = {1: "1 - High", 2: "2 - Medium", 3: "3 - Low"}
        if row:
            d = dict(row)
            return {
                "impact": level_labels.get(i_lvl, str(impact)),
                "urgency": level_labels.get(u_lvl, str(urgency)),
                "impact_level": i_lvl,
                "urgency_level": u_lvl,
                "priority": d["priority_code"],
                "priority_label": d["priority_label"],
                "sla_target_hours": float(d["resolution_sla_hours"]),
                "resolution_sla_hours": float(d["resolution_sla_hours"]),
                "response_sla_hours": float(d["response_sla_hours"]),
            }
        else:
            # Fallback default
            return {
                "impact": level_labels.get(i_lvl, str(impact)),
                "urgency": level_labels.get(u_lvl, str(urgency)),
                "impact_level": i_lvl,
                "urgency_level": u_lvl,
                "priority": "P3",
                "priority_label": "P3 - Moderate",
                "sla_target_hours": 8.0,
                "resolution_sla_hours": 8.0,
                "response_sla_hours": 1.0,
            }

    @staticmethod
    def _normalize_level(val: Any) -> int:
        s = str(val or "").strip().lower()
        if s.startswith("1") or "high" in s or "critical" in s:
            return 1
        elif s.startswith("2") or "medium" in s or "moderate" in s:
            return 2
        elif s.startswith("3") or "low" in s:
            return 3
        return 3

    # ------------------------------------------------------------------------
    # 3. SLA POLICIES & OPERATIONAL SCHEDULES
    # ------------------------------------------------------------------------

    def list_sla_policies(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            q = "SELECT * FROM config_sla_policies"
            if not include_inactive:
                q += " WHERE is_active = 1"
            q += " ORDER BY is_default DESC, name ASC"
            cursor.execute(q)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["pause_states"] = json.loads(d["pause_states"]) if d.get("pause_states") else []
                d["pause_reasons"] = json.loads(d["pause_reasons"]) if d.get("pause_reasons") else []
                result.append(d)
            return result

    def get_sla_policy(self, identifier: Union[int, str]) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if str(identifier).isdigit():
                cursor.execute("SELECT * FROM config_sla_policies WHERE id = ?", (int(identifier),))
            else:
                cursor.execute("SELECT * FROM config_sla_policies WHERE name = ?", (str(identifier),))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["pause_states"] = json.loads(d["pause_states"]) if d.get("pause_states") else []
            d["pause_reasons"] = json.loads(d["pause_reasons"]) if d.get("pause_reasons") else []
            return d

    def get_default_sla_policy(self) -> Dict[str, Any]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM config_sla_policies WHERE is_default = 1 AND is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT * FROM config_sla_policies WHERE is_active = 1 LIMIT 1")
                row = cursor.fetchone()
            if row:
                d = dict(row)
                d["pause_states"] = json.loads(d["pause_states"]) if d.get("pause_states") else []
                d["pause_reasons"] = json.loads(d["pause_reasons"]) if d.get("pause_reasons") else []
                return d
            return {
                "name": "Fallback 24x7 Policy",
                "schedule_type": "24x7",
                "pause_states": ["On Hold"],
                "p1_resolution_hours": 1.0,
                "p2_resolution_hours": 4.0,
                "p3_resolution_hours": 8.0,
                "p4_resolution_hours": 24.0,
            }

    def create_sla_policy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.datetime.utcnow().isoformat()
        is_default = 1 if data.get("is_default") else 0
        pause_states = json.dumps(data.get("pause_states", ["On Hold"]))
        pause_reasons = json.dumps(data.get("pause_reasons", ["Awaiting Caller", "Awaiting Vendor"]))

        with db.get_connection() as conn:
            cursor = conn.cursor()
            if is_default == 1:
                cursor.execute("UPDATE config_sla_policies SET is_default = 0")
            cursor.execute("""
                INSERT INTO config_sla_policies (
                    name, description, schedule_type, business_start_hour, business_end_hour,
                    workdays, timezone, pause_states, pause_reasons,
                    p1_resolution_hours, p2_resolution_hours, p3_resolution_hours, p4_resolution_hours,
                    p1_response_hours, p2_response_hours, p3_response_hours, p4_response_hours,
                    is_default, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["name"].strip(),
                data.get("description", ""),
                data.get("schedule_type", "24x7"),
                data.get("business_start_hour", 9),
                data.get("business_end_hour", 18),
                data.get("workdays", "1,2,3,4,5"),
                data.get("timezone", "UTC"),
                pause_states,
                pause_reasons,
                data.get("p1_resolution_hours", 1.0),
                data.get("p2_resolution_hours", 4.0),
                data.get("p3_resolution_hours", 8.0),
                data.get("p4_resolution_hours", 24.0),
                data.get("p1_response_hours", 0.25),
                data.get("p2_response_hours", 1.0),
                data.get("p3_response_hours", 2.0),
                data.get("p4_response_hours", 4.0),
                is_default,
                1 if data.get("is_active", True) else 0,
                now, now
            ))
            policy_id = cursor.lastrowid
        return self.get_sla_policy(policy_id)

    def update_sla_policy(self, policy_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_sla_policy(policy_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"SLA Policy '{policy_id}' not found")
        now = datetime.datetime.utcnow().isoformat()

        is_default = (1 if data["is_default"] else 0) if "is_default" in data and data["is_default"] is not None else existing["is_default"]
        pause_states = json.dumps(data["pause_states"]) if "pause_states" in data and data["pause_states"] is not None else json.dumps(existing["pause_states"])
        pause_reasons = json.dumps(data["pause_reasons"]) if "pause_reasons" in data and data["pause_reasons"] is not None else json.dumps(existing["pause_reasons"])

        with db.get_connection() as conn:
            cursor = conn.cursor()
            if is_default == 1:
                cursor.execute("UPDATE config_sla_policies SET is_default = 0 WHERE id != ?", (policy_id,))
            cursor.execute("""
                UPDATE config_sla_policies SET
                    name = COALESCE(?, name),
                    description = COALESCE(?, description),
                    schedule_type = COALESCE(?, schedule_type),
                    business_start_hour = COALESCE(?, business_start_hour),
                    business_end_hour = COALESCE(?, business_end_hour),
                    workdays = COALESCE(?, workdays),
                    timezone = COALESCE(?, timezone),
                    pause_states = ?,
                    pause_reasons = ?,
                    p1_resolution_hours = COALESCE(?, p1_resolution_hours),
                    p2_resolution_hours = COALESCE(?, p2_resolution_hours),
                    p3_resolution_hours = COALESCE(?, p3_resolution_hours),
                    p4_resolution_hours = COALESCE(?, p4_resolution_hours),
                    p1_response_hours = COALESCE(?, p1_response_hours),
                    p2_response_hours = COALESCE(?, p2_response_hours),
                    p3_response_hours = COALESCE(?, p3_response_hours),
                    p4_response_hours = COALESCE(?, p4_response_hours),
                    is_default = ?,
                    is_active = COALESCE(?, is_active),
                    updated_at = ?
                WHERE id = ?
            """, (
                data.get("name"),
                data.get("description"),
                data.get("schedule_type"),
                data.get("business_start_hour"),
                data.get("business_end_hour"),
                data.get("workdays"),
                data.get("timezone"),
                pause_states,
                pause_reasons,
                data.get("p1_resolution_hours"),
                data.get("p2_resolution_hours"),
                data.get("p3_resolution_hours"),
                data.get("p4_resolution_hours"),
                data.get("p1_response_hours"),
                data.get("p2_response_hours"),
                data.get("p3_response_hours"),
                data.get("p4_response_hours"),
                is_default,
                (1 if data.get("is_active") else 0) if data.get("is_active") is not None else None,
                now,
                policy_id
            ))
        return self.get_sla_policy(policy_id)

    def delete_sla_policy(self, policy_id: int) -> bool:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_sla_policies WHERE id = ?", (policy_id,))
            return cursor.rowcount > 0

    def calculate_sla_due_date(
        self,
        created_dt: datetime.datetime,
        priority: str,
        policy_id: Optional[int] = None,
        sla_hours_override: Optional[float] = None
    ) -> Tuple[datetime.datetime, float]:
        """Calculates SLA due date based on SLA policy and schedule (24x7 or Business Hours)."""
        policy = self.get_sla_policy(policy_id) if policy_id else self.get_default_sla_policy()
        p_clean = (priority or "P3").strip().upper()

        if sla_hours_override is not None and sla_hours_override > 0:
            target_hours = float(sla_hours_override)
        else:
            hours_map = {
                "P1": policy.get("p1_resolution_hours", 1.0),
                "P2": policy.get("p2_resolution_hours", 4.0),
                "P3": policy.get("p3_resolution_hours", 8.0),
                "P4": policy.get("p4_resolution_hours", 24.0),
            }
            target_hours = float(hours_map.get(p_clean, 8.0))

        schedule_type = policy.get("schedule_type", "24x7")
        if schedule_type == "24x7":
            return created_dt + datetime.timedelta(hours=target_hours), target_hours

        # Business Hours Schedule (e.g. 09:00 - 18:00, Mon-Fri)
        b_start = int(policy.get("business_start_hour", 9))
        b_end = int(policy.get("business_end_hour", 18))
        workdays_str = str(policy.get("workdays", "1,2,3,4,5"))
        workdays = set(int(d.strip()) for d in workdays_str.split(",") if d.strip().isdigit())

        current = created_dt
        remaining_minutes = target_hours * 60.0

        # Advance minute by minute / block by block within operational window
        while remaining_minutes > 0:
            iso_weekday = current.isoweekday()  # 1=Mon, 7=Sun
            if iso_weekday not in workdays or current.hour < b_start:
                # Fast forward to next business day start
                if iso_weekday not in workdays or current.hour >= b_end:
                    current = current.replace(hour=b_start, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                else:
                    current = current.replace(hour=b_start, minute=0, second=0, microsecond=0)
                continue

            if current.hour >= b_end:
                current = current.replace(hour=b_start, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                continue

            # In business window: compute remaining window for the day
            end_of_day = current.replace(hour=b_end, minute=0, second=0, microsecond=0)
            window_minutes = (end_of_day - current).total_seconds() / 60.0

            if remaining_minutes <= window_minutes:
                current = current + datetime.timedelta(minutes=remaining_minutes)
                remaining_minutes = 0
            else:
                remaining_minutes -= window_minutes
                current = current.replace(hour=b_start, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)

        return current, target_hours

    # ------------------------------------------------------------------------
    # 4. RESOLUTION CODES & ROOT CAUSE MASTER DATA
    # ------------------------------------------------------------------------

    def list_resolution_codes(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            q = "SELECT * FROM config_resolution_codes"
            if not include_inactive:
                q += " WHERE is_active = 1"
            q += " ORDER BY code ASC"
            cursor.execute(q)
            rows = cursor.fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d["root_cause_options"] = json.loads(d["root_cause_options"]) if d.get("root_cause_options") else []
                res.append(d)
            return res

    def get_resolution_code(self, identifier: Union[int, str]) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if str(identifier).isdigit():
                cursor.execute("SELECT * FROM config_resolution_codes WHERE id = ?", (int(identifier),))
            else:
                cursor.execute("SELECT * FROM config_resolution_codes WHERE code = ?", (str(identifier),))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["root_cause_options"] = json.loads(d["root_cause_options"]) if d.get("root_cause_options") else []
            return d

    def create_resolution_code(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.datetime.utcnow().isoformat()
        code = data["code"].strip()
        cat = data.get("category", "General")
        causes = json.dumps(data.get("root_cause_options", []))
        desc = data.get("description", "")
        is_active = 1 if data.get("is_active", True) else 0

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO config_resolution_codes (code, category, root_cause_options, description, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (code, cat, causes, desc, is_active, now, now))
            rc_id = cursor.lastrowid
        return self.get_resolution_code(rc_id)

    def update_resolution_code(self, code_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_resolution_code(code_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Resolution code '{code_id}' not found")
        now = datetime.datetime.utcnow().isoformat()

        causes = json.dumps(data["root_cause_options"]) if "root_cause_options" in data and data["root_cause_options"] is not None else json.dumps(existing["root_cause_options"])
        is_active = existing["is_active"] if data.get("is_active") is None else (1 if data.get("is_active") else 0)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE config_resolution_codes SET
                    code = COALESCE(?, code),
                    category = COALESCE(?, category),
                    root_cause_options = ?,
                    description = COALESCE(?, description),
                    is_active = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                data.get("code"),
                data.get("category"),
                causes,
                data.get("description"),
                is_active,
                now,
                code_id
            ))
        return self.get_resolution_code(code_id)

    def delete_resolution_code(self, code_id: int) -> bool:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_resolution_codes WHERE id = ?", (code_id,))
            return cursor.rowcount > 0

    # ------------------------------------------------------------------------
    # 5. TECHNICIANS, BILLING RATES & SUPPORT GROUPS
    # ------------------------------------------------------------------------

    def list_technicians(self, support_group: Optional[str] = None, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            q = "SELECT * FROM config_technicians WHERE 1=1"
            params: List[Any] = []
            if support_group:
                q += " AND support_group = ?"
                params.append(support_group)
            if not include_inactive:
                q += " AND is_active = 1"
            q += " ORDER BY name ASC"
            cursor.execute(q, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_technician(self, identifier: Union[int, str]) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if str(identifier).isdigit():
                cursor.execute("SELECT * FROM config_technicians WHERE id = ?", (int(identifier),))
            else:
                cursor.execute("SELECT * FROM config_technicians WHERE email = ? OR name = ?", (str(identifier), str(identifier)))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_technician(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.datetime.utcnow().isoformat()
        name = data["name"].strip()
        email = data["email"].strip().lower()
        rate = float(data.get("hourly_rate", 65.0))
        group = data.get("support_group", "Service Desk")
        role = data.get("role", "Technician")
        is_active = 1 if data.get("is_active", True) else 0

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO config_technicians (name, email, hourly_rate, support_group, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, email, rate, group, role, is_active, now, now))
            tech_id = cursor.lastrowid
        return self.get_technician(tech_id)

    def update_technician(self, tech_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_technician(tech_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Technician '{tech_id}' not found")
        now = datetime.datetime.utcnow().isoformat()
        is_active = existing["is_active"] if data.get("is_active") is None else (1 if data.get("is_active") else 0)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE config_technicians SET
                    name = COALESCE(?, name),
                    email = COALESCE(?, email),
                    hourly_rate = COALESCE(?, hourly_rate),
                    support_group = COALESCE(?, support_group),
                    role = COALESCE(?, role),
                    is_active = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                data.get("name"),
                data.get("email"),
                data.get("hourly_rate"),
                data.get("support_group"),
                data.get("role"),
                is_active,
                now,
                tech_id
            ))
        return self.get_technician(tech_id)

    def delete_technician(self, tech_id: int) -> bool:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_technicians WHERE id = ?", (tech_id,))
            return cursor.rowcount > 0

    def get_technician_rate(self, name_or_email: str) -> float:
        """Looks up technician billing rate by name or email. Returns 65.0 default if not found."""
        tech = self.get_technician(name_or_email)
        if tech and tech.get("hourly_rate") is not None:
            return float(tech["hourly_rate"])
        return 65.0

    # ------------------------------------------------------------------------
    # 6. BUSINESS RULES & AUTOMATED ROUTING ENGINE
    # ------------------------------------------------------------------------

    def list_business_rules(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            q = "SELECT * FROM config_business_rules"
            if not include_inactive:
                q += " WHERE is_active = 1"
            q += " ORDER BY order_num ASC, id ASC"
            cursor.execute(q)
            rows = cursor.fetchall()
            rules = []
            for r in rows:
                d = dict(r)
                d["criteria"] = json.loads(d["criteria"]) if d.get("criteria") else {}
                d["actions"] = json.loads(d["actions"]) if d.get("actions") else {}
                rules.append(d)
            return rules

    def get_business_rule(self, rule_id: int) -> Optional[Dict[str, Any]]:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM config_business_rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["criteria"] = json.loads(d["criteria"]) if d.get("criteria") else {}
            d["actions"] = json.loads(d["actions"]) if d.get("actions") else {}
            return d

    def create_business_rule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.datetime.utcnow().isoformat()
        name = data["name"].strip()
        desc = data.get("description", "")
        order_num = int(data.get("order_num", 10))
        is_active = 1 if data.get("is_active", True) else 0
        criteria = json.dumps(data.get("criteria", {}))
        actions = json.dumps(data.get("actions", {}))

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO config_business_rules (name, description, order_num, is_active, criteria, actions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, desc, order_num, is_active, criteria, actions, now, now))
            rule_id = cursor.lastrowid
        return self.get_business_rule(rule_id)

    def update_business_rule(self, rule_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_business_rule(rule_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Business rule '{rule_id}' not found")
        now = datetime.datetime.utcnow().isoformat()

        criteria = json.dumps(data["criteria"]) if "criteria" in data and data["criteria"] is not None else json.dumps(existing["criteria"])
        actions = json.dumps(data["actions"]) if "actions" in data and data["actions"] is not None else json.dumps(existing["actions"])
        is_active = existing["is_active"] if data.get("is_active") is None else (1 if data.get("is_active") else 0)

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE config_business_rules SET
                    name = COALESCE(?, name),
                    description = COALESCE(?, description),
                    order_num = COALESCE(?, order_num),
                    is_active = ?,
                    criteria = ?,
                    actions = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                data.get("name"),
                data.get("description"),
                data.get("order_num"),
                is_active,
                criteria,
                actions,
                now,
                rule_id
            ))
        return self.get_business_rule(rule_id)

    def delete_business_rule(self, rule_id: int) -> bool:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_business_rules WHERE id = ?", (rule_id,))
            return cursor.rowcount > 0

    def evaluate_business_rules(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """Evaluates auto-priority matrix and dynamic business rules on incident payload."""
        data = dict(payload)
        applied_rules: List[str] = []

        # 1. Dynamic Auto-Priority Matrix Calculation
        impact = data.get("impact", "2 - Medium")
        urgency = data.get("urgency", "2 - Medium")
        matrix_res = self.compute_priority(impact, urgency)

        if not data.get("priority"):
            data["priority"] = matrix_res["priority"]
            data["sla_target_hours"] = matrix_res["sla_target_hours"]
            applied_rules.append(f"AUTO_PRIORITY_MATRIX_{matrix_res['priority']}")
        else:
            p_clean = data["priority"].strip().upper()
            data["priority"] = p_clean
            # Read SLA from matrix for this priority or fallback
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT resolution_sla_hours FROM config_priority_matrix WHERE priority_code = ? LIMIT 1", (p_clean,))
                p_row = cursor.fetchone()
                if p_row:
                    data["sla_target_hours"] = float(p_row["resolution_sla_hours"])
                else:
                    p_sla_map = {"P1": 1.0, "P2": 4.0, "P3": 8.0, "P4": 24.0}
                    data["sla_target_hours"] = p_sla_map.get(p_clean, 4.0)

        # 2. Dynamic Rules Evaluation in Order of order_num
        active_rules = self.list_business_rules(include_inactive=False)
        for rule in active_rules:
            criteria = rule.get("criteria", {})
            actions = rule.get("actions", {})
            rule_name = rule.get("name", f"RULE_{rule['id']}")

            if self._matches_criteria(data, criteria):
                rule_slug = rule_name.upper().replace(" ", "_").replace("-", "_")
                # Apply Actions
                if "priority_bump" in actions:
                    bump_count = int(actions["priority_bump"])
                    current_p = data.get("priority", "P3")
                    bump_map = {"P4": "P3", "P3": "P2", "P2": "P1", "P1": "P1"}
                    new_p = current_p
                    for _ in range(bump_count):
                        new_p = bump_map.get(new_p, new_p)
                    if new_p != current_p:
                        data["priority"] = new_p
                        applied_rules.append(f"VIP_CALLER_ESCALATED_{current_p}_TO_{new_p}")
                    else:
                        applied_rules.append(rule_slug)

                if "priority" in actions and not actions.get("priority_bump"):
                    data["priority"] = str(actions["priority"]).strip().upper()
                    applied_rules.append(f"{rule_slug}_SET_PRIORITY_{data['priority']}")

                if "assignment_group" in actions:
                    if not data.get("assignment_group") or actions.get("overwrite_group"):
                        data["assignment_group"] = actions["assignment_group"]
                        grp = actions["assignment_group"]
                        if grp == "Major Incident Response Team":
                            applied_rules.append("P1_AUTO_MAJOR_INCIDENT_TEAM")
                        elif grp == "Cybersecurity SOC":
                            applied_rules.append("SECURITY_ROUTED_TO_SOC")
                        elif grp == "Database Engineering":
                            applied_rules.append("DB_ROUTED_TO_DBA")
                        elif grp == "Platform & Cloud Ops":
                            applied_rules.append("INFRA_ROUTED_TO_PLATFORM")
                        elif grp == "Data Center Infrastructure":
                            applied_rules.append("HARDWARE_ROUTED_TO_DC")
                        else:
                            applied_rules.append(f"{rule_slug}_ROUTED_{grp.upper().replace(' ', '_')}")

                if "assigned_to" in actions:
                    if not data.get("assigned_to") or actions.get("overwrite_assignee"):
                        data["assigned_to"] = actions["assigned_to"]
                        applied_rules.append(f"{rule_slug}_ASSIGNED_{actions['assigned_to']}")

                if "sla_target_hours" in actions:
                    data["sla_target_hours"] = float(actions["sla_target_hours"])

                if "custom_fields" in actions and isinstance(actions["custom_fields"], dict):
                    cfields = data.get("custom_fields", {})
                    cfields.update(actions["custom_fields"])
                    data["custom_fields"] = cfields

        return data, applied_rules

    def _matches_criteria(self, data: Dict[str, Any], criteria: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bool:
        """Recursively validates criteria conditions against incident payload."""
        if not criteria:
            return False

        if isinstance(criteria, list):
            # All conditions in the list must match (AND logic)
            return all(self._matches_condition(data, cond) for cond in criteria)
        elif isinstance(criteria, dict):
            if "field" in criteria and "operator" in criteria:
                return self._matches_condition(data, criteria)
            else:
                # Key-value simple matching: {"category": "Security"}
                for k, v in criteria.items():
                    val = str(data.get(k) or "").strip().lower()
                    target = str(v).strip().lower()
                    if target not in val:
                        return False
                return True
        return False

    def _matches_condition(self, data: Dict[str, Any], cond: Dict[str, Any]) -> bool:
        field = cond.get("field", "")
        op = cond.get("operator", "equals").lower()
        field_val = data.get(field)
        val_str = str(field_val or "").strip().lower()

        if op in ("equals", "eq"):
            target = str(cond.get("value") or "").strip().lower()
            return val_str == target
        elif op in ("not_equals", "neq"):
            target = str(cond.get("value") or "").strip().lower()
            return val_str != target
        elif op in ("contains", "has"):
            target = str(cond.get("value") or "").strip().lower()
            return target in val_str
        elif op == "not_contains":
            target = str(cond.get("value") or "").strip().lower()
            return target not in val_str
        elif op == "contains_any":
            values = cond.get("values", [])
            return any(str(v).strip().lower() in val_str for v in values)
        elif op == "in":
            values = [str(v).strip().lower() for v in cond.get("values", [])]
            return val_str in values
        elif op == "starts_with":
            target = str(cond.get("value") or "").strip().lower()
            return val_str.startswith(target)
        elif op == "ends_with":
            target = str(cond.get("value") or "").strip().lower()
            return val_str.endswith(target)
        return False


# Global singleton instance
config_engine = ConfigEngine()


# ============================================================================
# FASTAPI ROUTER ENDPOINTS (/api/v2/config/...)
# ============================================================================

# --- 1. TAXONOMY CATEGORIES ---

@config_router.get("/taxonomy/categories", tags=["Configuration & Master Data"])
def list_categories(include_inactive: bool = Query(False, description="Include inactive categories")) -> List[Dict[str, Any]]:
    """Lists all master categories."""
    return config_engine.list_categories(include_inactive=include_inactive)

@config_router.post("/taxonomy/categories", status_code=status.HTTP_201_CREATED, tags=["Configuration & Master Data"])
def create_category(payload: CategoryCreate) -> Dict[str, Any]:
    """Creates a new category in master data."""
    raw = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return config_engine.create_category(raw)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Category with name '{payload.name}' already exists")

@config_router.put("/taxonomy/categories/{category_id}", tags=["Configuration & Master Data"])
def update_category_by_path(category_id: int, payload: CategoryUpdate) -> Dict[str, Any]:
    """Updates category by path ID."""
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_category(category_id, raw)

@config_router.put("/taxonomy/categories", tags=["Configuration & Master Data"])
def update_category_by_body(payload: CategoryUpdate) -> Dict[str, Any]:
    """Updates category with id in body."""
    if not payload.id:
        raise HTTPException(status_code=400, detail="Missing required 'id' in request body")
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_category(payload.id, raw)

@config_router.delete("/taxonomy/categories/{category_id}", tags=["Configuration & Master Data"])
def delete_category_by_path(category_id: int) -> Dict[str, Any]:
    """Deletes category by path ID."""
    deleted = config_engine.delete_category(category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Category '{category_id}' not found")
    return {"success": True, "message": f"Category {category_id} deleted"}

@config_router.delete("/taxonomy/categories", tags=["Configuration & Master Data"])
def delete_category_by_query(id: Optional[int] = Query(None, description="Category ID to delete")) -> Dict[str, Any]:
    """Deletes category by query parameter id."""
    if not id:
        raise HTTPException(status_code=400, detail="Missing required query parameter 'id'")
    deleted = config_engine.delete_category(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Category '{id}' not found")
    return {"success": True, "message": f"Category {id} deleted"}

@config_router.post("/taxonomy/categories/{category_id}/toggle-active", tags=["Configuration & Master Data"])
def toggle_category(category_id: int) -> Dict[str, Any]:
    """Toggles active/inactive status of a category."""
    return config_engine.toggle_category_active(category_id)


# --- 2. TAXONOMY SUBCATEGORIES ---

@config_router.get("/taxonomy/subcategories", tags=["Configuration & Master Data"])
def list_subcategories(
    category_id: Optional[int] = Query(None, description="Filter by parent category ID"),
    include_inactive: bool = Query(False, description="Include inactive subcategories")
) -> List[Dict[str, Any]]:
    """Lists subcategories with parent category mapping."""
    return config_engine.list_subcategories(category_id=category_id, include_inactive=include_inactive)

@config_router.post("/taxonomy/subcategories", status_code=status.HTTP_201_CREATED, tags=["Configuration & Master Data"])
def create_subcategory(payload: SubcategoryCreate) -> Dict[str, Any]:
    """Creates a new subcategory linked to a category."""
    raw = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return config_engine.create_subcategory(raw)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Subcategory '{payload.name}' already exists in this category")

@config_router.put("/taxonomy/subcategories/{subcategory_id}", tags=["Configuration & Master Data"])
def update_subcategory_by_path(subcategory_id: int, payload: SubcategoryUpdate) -> Dict[str, Any]:
    """Updates subcategory by path ID."""
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_subcategory(subcategory_id, raw)

@config_router.delete("/taxonomy/subcategories/{subcategory_id}", tags=["Configuration & Master Data"])
def delete_subcategory_by_path(subcategory_id: int) -> Dict[str, Any]:
    """Deletes subcategory by path ID."""
    deleted = config_engine.delete_subcategory(subcategory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Subcategory '{subcategory_id}' not found")
    return {"success": True, "message": f"Subcategory {subcategory_id} deleted"}

@config_router.post("/taxonomy/subcategories/{subcategory_id}/toggle-active", tags=["Configuration & Master Data"])
def toggle_subcategory(subcategory_id: int) -> Dict[str, Any]:
    """Toggles active status of a subcategory."""
    return config_engine.toggle_subcategory_active(subcategory_id)


# --- 3. TAXONOMY ITEMS ---

@config_router.get("/taxonomy/items", tags=["Configuration & Master Data"])
def list_items(
    subcategory_id: Optional[int] = Query(None, description="Filter by parent subcategory ID"),
    include_inactive: bool = Query(False, description="Include inactive items")
) -> List[Dict[str, Any]]:
    """Lists items with hierarchy mapping."""
    return config_engine.list_items(subcategory_id=subcategory_id, include_inactive=include_inactive)

@config_router.post("/taxonomy/items", status_code=status.HTTP_201_CREATED, tags=["Configuration & Master Data"])
def create_item(payload: ItemCreate) -> Dict[str, Any]:
    """Creates a new tier-3 item."""
    raw = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return config_engine.create_item(raw)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Item '{payload.name}' already exists in this subcategory")

@config_router.put("/taxonomy/items/{item_id}", tags=["Configuration & Master Data"])
def update_item_by_path(item_id: int, payload: ItemUpdate) -> Dict[str, Any]:
    """Updates item by path ID."""
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_item(item_id, raw)

@config_router.delete("/taxonomy/items/{item_id}", tags=["Configuration & Master Data"])
def delete_item_by_path(item_id: int) -> Dict[str, Any]:
    """Deletes item by path ID."""
    deleted = config_engine.delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
    return {"success": True, "message": f"Item {item_id} deleted"}

@config_router.post("/taxonomy/items/{item_id}/toggle-active", tags=["Configuration & Master Data"])
def toggle_item(item_id: int) -> Dict[str, Any]:
    """Toggles active status of an item."""
    return config_engine.toggle_item_active(item_id)


# --- 4. PRIORITY MATRIX ---

@config_router.get("/priority-matrix", tags=["Configuration & Master Data"])
def get_priority_matrix() -> List[Dict[str, Any]]:
    """Returns the full 3x3 Impact x Urgency priority matrix configuration."""
    return config_engine.list_priority_matrix()

@config_router.put("/priority-matrix", tags=["Configuration & Master Data"])
def update_priority_matrix(payload: Union[PriorityMatrixUpdate, List[PriorityMatrixUpdate]]) -> List[Dict[str, Any]]:
    """Updates one or multiple priority matrix cells."""
    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        config_engine.update_priority_matrix_entry(
            impact_level=item.impact_level,
            urgency_level=item.urgency_level,
            priority_code=item.priority_code,
            priority_label=item.priority_label,
            resolution_sla_hours=item.resolution_sla_hours,
            response_sla_hours=item.response_sla_hours,
        )
    return config_engine.list_priority_matrix()

@config_router.put("/priority-matrix/{impact_level}/{urgency_level}", tags=["Configuration & Master Data"])
def update_priority_matrix_cell(impact_level: int, urgency_level: int, payload: PriorityMatrixUpdate) -> Dict[str, Any]:
    """Updates specific matrix cell by impact and urgency level."""
    return config_engine.update_priority_matrix_entry(
        impact_level=impact_level,
        urgency_level=urgency_level,
        priority_code=payload.priority_code,
        priority_label=payload.priority_label,
        resolution_sla_hours=payload.resolution_sla_hours,
        response_sla_hours=payload.response_sla_hours,
    )


# --- 5. RESOLUTION CODES ---

@config_router.get("/resolution-codes", tags=["Configuration & Master Data"])
def list_resolution_codes(include_inactive: bool = Query(False, description="Include inactive codes")) -> List[Dict[str, Any]]:
    """Lists resolution codes and associated root cause options."""
    return config_engine.list_resolution_codes(include_inactive=include_inactive)

@config_router.post("/resolution-codes", status_code=status.HTTP_201_CREATED, tags=["Configuration & Master Data"])
def create_resolution_code(payload: ResolutionCodeCreate) -> Dict[str, Any]:
    """Creates a new resolution code master record."""
    raw = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return config_engine.create_resolution_code(raw)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Resolution code '{payload.code}' already exists")

@config_router.put("/resolution-codes/{id}", tags=["Configuration & Master Data"])
def update_resolution_code(id: int, payload: ResolutionCodeUpdate) -> Dict[str, Any]:
    """Updates resolution code by path ID."""
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_resolution_code(id, raw)

@config_router.delete("/resolution-codes/{id}", tags=["Configuration & Master Data"])
def delete_resolution_code_by_path(id: int) -> Dict[str, Any]:
    """Deletes resolution code by path ID."""
    deleted = config_engine.delete_resolution_code(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Resolution code '{id}' not found")
    return {"success": True, "message": f"Resolution code {id} deleted"}

@config_router.delete("/resolution-codes", tags=["Configuration & Master Data"])
def delete_resolution_code_by_query(id: Optional[int] = Query(None, description="Resolution code ID to delete")) -> Dict[str, Any]:
    """Deletes resolution code by query parameter id."""
    if not id:
        raise HTTPException(status_code=400, detail="Missing required query parameter 'id'")
    deleted = config_engine.delete_resolution_code(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Resolution code '{id}' not found")
    return {"success": True, "message": f"Resolution code {id} deleted"}


# --- 6. SLA POLICIES ---

@config_router.get("/sla-policies", tags=["Configuration & Master Data"])
def list_sla_policies(include_inactive: bool = Query(False, description="Include inactive SLA policies")) -> List[Dict[str, Any]]:
    """Lists SLA policies and operational schedules."""
    return config_engine.list_sla_policies(include_inactive=include_inactive)

@config_router.post("/sla-policies", status_code=status.HTTP_201_CREATED, tags=["Configuration & Master Data"])
def create_sla_policy(payload: SLAPolicyCreate) -> Dict[str, Any]:
    """Creates a new SLA policy."""
    raw = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return config_engine.create_sla_policy(raw)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"SLA policy '{payload.name}' already exists")

@config_router.put("/sla-policies/{id}", tags=["Configuration & Master Data"])
def update_sla_policy_by_path(id: int, payload: SLAPolicyUpdate) -> Dict[str, Any]:
    """Updates SLA policy by path ID."""
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_sla_policy(id, raw)

@config_router.put("/sla-policies", tags=["Configuration & Master Data"])
def update_sla_policy_by_body(payload: SLAPolicyUpdate) -> Dict[str, Any]:
    """Updates SLA policy with id in body."""
    if not payload.id:
        raise HTTPException(status_code=400, detail="Missing required 'id' in request body")
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_sla_policy(payload.id, raw)

@config_router.delete("/sla-policies/{id}", tags=["Configuration & Master Data"])
def delete_sla_policy(id: int) -> Dict[str, Any]:
    """Deletes SLA policy by path ID."""
    deleted = config_engine.delete_sla_policy(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"SLA Policy '{id}' not found")
    return {"success": True, "message": f"SLA Policy {id} deleted"}


# --- 7. TECHNICIANS & BILLING RATES ---

@config_router.get("/technicians", tags=["Configuration & Master Data"])
def list_technicians(
    support_group: Optional[str] = Query(None, description="Filter by support group"),
    include_inactive: bool = Query(False, description="Include inactive technicians")
) -> List[Dict[str, Any]]:
    """Lists technicians, assigned support groups, and billing rates ($/hr)."""
    return config_engine.list_technicians(support_group=support_group, include_inactive=include_inactive)

@config_router.post("/technicians", status_code=status.HTTP_201_CREATED, tags=["Configuration & Master Data"])
def create_technician(payload: TechnicianCreate) -> Dict[str, Any]:
    """Registers a technician with hourly billing rate and support group."""
    raw = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return config_engine.create_technician(raw)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Technician with email '{payload.email}' already exists")

@config_router.put("/technicians/{id}", tags=["Configuration & Master Data"])
def update_technician_by_path(id: int, payload: TechnicianUpdate) -> Dict[str, Any]:
    """Updates technician by path ID."""
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_technician(id, raw)

@config_router.put("/technicians", tags=["Configuration & Master Data"])
def update_technician_by_body(payload: TechnicianUpdate) -> Dict[str, Any]:
    """Updates technician with id in body."""
    if not payload.id:
        raise HTTPException(status_code=400, detail="Missing required 'id' in request body")
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_technician(payload.id, raw)

@config_router.delete("/technicians/{id}", tags=["Configuration & Master Data"])
def delete_technician_by_path(id: int) -> Dict[str, Any]:
    """Deletes technician by path ID."""
    deleted = config_engine.delete_technician(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Technician '{id}' not found")
    return {"success": True, "message": f"Technician {id} deleted"}

@config_router.delete("/technicians", tags=["Configuration & Master Data"])
def delete_technician_by_query(id: Optional[int] = Query(None, description="Technician ID to delete")) -> Dict[str, Any]:
    """Deletes technician by query parameter id."""
    if not id:
        raise HTTPException(status_code=400, detail="Missing required query parameter 'id'")
    deleted = config_engine.delete_technician(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Technician '{id}' not found")
    return {"success": True, "message": f"Technician {id} deleted"}


# --- 8. BUSINESS RULES ---

@config_router.get("/business-rules", tags=["Configuration & Master Data"])
def list_business_rules(include_inactive: bool = Query(False, description="Include inactive rules")) -> List[Dict[str, Any]]:
    """Lists criteria-based business rules ordered by execution sequence."""
    return config_engine.list_business_rules(include_inactive=include_inactive)

@config_router.post("/business-rules", status_code=status.HTTP_201_CREATED, tags=["Configuration & Master Data"])
def create_business_rule(payload: BusinessRuleCreate) -> Dict[str, Any]:
    """Creates a new automated business routing/classification rule."""
    raw = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return config_engine.create_business_rule(raw)

@config_router.put("/business-rules/{id}", tags=["Configuration & Master Data"])
def update_business_rule_by_path(id: int, payload: BusinessRuleUpdate) -> Dict[str, Any]:
    """Updates business rule by path ID."""
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_business_rule(id, raw)

@config_router.put("/business-rules", tags=["Configuration & Master Data"])
def update_business_rule_by_body(payload: BusinessRuleUpdate) -> Dict[str, Any]:
    """Updates business rule with id in body."""
    if not payload.id:
        raise HTTPException(status_code=400, detail="Missing required 'id' in request body")
    raw = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    return config_engine.update_business_rule(payload.id, raw)

@config_router.delete("/business-rules/{id}", tags=["Configuration & Master Data"])
def delete_business_rule_by_path(id: int) -> Dict[str, Any]:
    """Deletes business rule by path ID."""
    deleted = config_engine.delete_business_rule(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Business rule '{id}' not found")
    return {"success": True, "message": f"Business rule {id} deleted"}

@config_router.delete("/business-rules", tags=["Configuration & Master Data"])
def delete_business_rule_by_query(id: Optional[int] = Query(None, description="Business rule ID to delete")) -> Dict[str, Any]:
    """Deletes business rule by query parameter id."""
    if not id:
        raise HTTPException(status_code=400, detail="Missing required query parameter 'id'")
    deleted = config_engine.delete_business_rule(id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Business rule '{id}' not found")
    return {"success": True, "message": f"Business rule {id} deleted"}


# ============================================================================
# COMPREHENSIVE UNIT TESTS UNDER IF __NAME__ == '__main__':
# ============================================================================

if __name__ == "__main__":
    import unittest
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(config_router)
    client = TestClient(test_app)

    class TestMasterDataConfigEngine(unittest.TestCase):
        def setUp(self):
            # Ensure schema and defaults are initialized
            config_engine.init_schema()
            config_engine.seed_defaults_if_empty()
            # Clean up test artifacts if they exist from prior runs
            cat = config_engine.get_category("DevOps & SRE")
            if cat:
                config_engine.delete_category(cat["id"])
            rc = config_engine.get_resolution_code("Security Quarantine Isolation")
            if rc:
                config_engine.delete_resolution_code(rc["id"])
            tech = config_engine.get_technician("nadia.v@opennow.io")
            if tech:
                config_engine.delete_technician(tech["id"])
            for r in config_engine.list_business_rules(include_inactive=True):
                if "SAP Basis" in r["name"]:
                    config_engine.delete_business_rule(r["id"])
            for pol in config_engine.list_sla_policies(include_inactive=True):
                if "Financial Core Ultra" in pol["name"]:
                    config_engine.delete_sla_policy(pol["id"])

        def test_01_taxonomy_crud_and_toggle(self):
            # Create Category
            res = client.post("/api/v2/config/taxonomy/categories", json={
                "name": "DevOps & SRE",
                "code": "DEVOPS_SRE",
                "description": "Continuous Integration & Delivery Pipelines"
            })
            self.assertEqual(res.status_code, 201)
            cat = res.json()
            cat_id = cat["id"]
            self.assertEqual(cat["name"], "DevOps & SRE")
            self.assertTrue(cat["is_active"])

            # Create Subcategory
            res_sub = client.post("/api/v2/config/taxonomy/subcategories", json={
                "category_id": cat_id,
                "name": "GitHub Actions",
                "code": "GH_ACTIONS",
                "description": "Hosted and self-hosted workflow runners"
            })
            self.assertEqual(res_sub.status_code, 201)
            sub = res_sub.json()
            sub_id = sub["id"]

            # Create Item
            res_item = client.post("/api/v2/config/taxonomy/items", json={
                "subcategory_id": sub_id,
                "name": "Self-Hosted Runner Offline",
                "code": "RUNNER_OFFLINE"
            })
            self.assertEqual(res_item.status_code, 201)
            item = res_item.json()
            item_id = item["id"]

            # Verify presence in dynamic taxonomy tree
            tree = config_engine.get_taxonomy_tree()
            self.assertIn("DevOps & SRE", tree["taxonomy"])
            self.assertIn("GitHub Actions", tree["taxonomy"]["DevOps & SRE"])
            self.assertIn("Self-Hosted Runner Offline", tree["taxonomy"]["DevOps & SRE"]["GitHub Actions"])

            # Toggle category inactive
            res_toggle = client.post(f"/api/v2/config/taxonomy/categories/{cat_id}/toggle-active")
            self.assertEqual(res_toggle.status_code, 200)
            self.assertFalse(res_toggle.json()["is_active"])

            # Verify excluded from active tree
            active_tree = config_engine.get_taxonomy_tree(include_inactive=False)
            self.assertNotIn("DevOps & SRE", active_tree["taxonomy"])

            # Cleanup
            client.delete(f"/api/v2/config/taxonomy/items/{item_id}")
            client.delete(f"/api/v2/config/taxonomy/subcategories/{sub_id}")
            client.delete(f"/api/v2/config/taxonomy/categories/{cat_id}")

        def test_02_priority_matrix_runtime_reflection(self):
            # Check default calculation for Impact 1 (High), Urgency 1 (High)
            p_default = config_engine.compute_priority("1 - High", "1 - High")
            self.assertEqual(p_default["priority"], "P1")
            self.assertEqual(p_default["sla_target_hours"], 1.0)

            # Update Priority Matrix cell: change Impact 1, Urgency 1 to SLA 0.5 hours
            res_upd = client.put("/api/v2/config/priority-matrix", json={
                "impact_level": 1,
                "urgency_level": 1,
                "priority_code": "P1",
                "priority_label": "P1 - Critical Ultra",
                "resolution_sla_hours": 0.5,
                "response_sla_hours": 0.1
            })
            self.assertEqual(res_upd.status_code, 200)

            # Verify immediate runtime reflection
            p_updated = config_engine.compute_priority(1, 1)
            self.assertEqual(p_updated["priority"], "P1")
            self.assertEqual(p_updated["sla_target_hours"], 0.5)
            self.assertEqual(p_updated["priority_label"], "P1 - Critical Ultra")

            # Reset back to 1.0
            client.put("/api/v2/config/priority-matrix", json={
                "impact_level": 1,
                "urgency_level": 1,
                "priority_code": "P1",
                "priority_label": "P1 - Critical",
                "resolution_sla_hours": 1.0,
                "response_sla_hours": 0.25
            })

        def test_03_sla_policies_and_business_hours(self):
            # List SLA policies
            res = client.get("/api/v2/config/sla-policies")
            self.assertEqual(res.status_code, 200)
            policies = res.json()
            self.assertGreaterEqual(len(policies), 1)

            # Create custom SLA policy
            res_create = client.post("/api/v2/config/sla-policies", json={
                "name": "Financial Core Ultra SLA",
                "schedule_type": "business_hours",
                "business_start_hour": 9,
                "business_end_hour": 17,
                "workdays": "1,2,3,4,5",
                "p1_resolution_hours": 2.0,
                "p2_resolution_hours": 6.0,
                "pause_states": ["On Hold", "Pending Vendor"]
            })
            self.assertEqual(res_create.status_code, 201)
            pol = res_create.json()
            pol_id = pol["id"]

            # Calculate SLA due date under business hours schedule
            # Friday at 16:30 (4:30 PM), with 2.0 resolution hours:
            # 30 mins remaining on Friday (until 17:00), remaining 90 mins carry over to Monday 09:00 + 1.5 hours = Monday 10:30!
            friday_1630 = datetime.datetime(2026, 10, 16, 16, 30)  # Oct 16, 2026 is Friday
            due_dt, target_h = config_engine.calculate_sla_due_date(friday_1630, "P1", policy_id=pol_id)
            self.assertEqual(target_h, 2.0)
            self.assertEqual(due_dt.year, 2026)
            self.assertEqual(due_dt.month, 10)
            self.assertEqual(due_dt.day, 19)  # Monday Oct 19
            self.assertEqual(due_dt.hour, 10)
            self.assertEqual(due_dt.minute, 30)

            # Cleanup
            client.delete(f"/api/v2/config/sla-policies/{pol_id}")

        def test_04_resolution_codes_crud(self):
            res = client.post("/api/v2/config/resolution-codes", json={
                "code": "Security Quarantine Isolation",
                "category": "Incident Response",
                "root_cause_options": ["Malicious Payload", "Suspicious Process", "Unauthorized Exfiltration"],
                "description": "Host was isolated from network to prevent lateral movement"
            })
            self.assertEqual(res.status_code, 201)
            rc = res.json()
            rc_id = rc["id"]
            self.assertEqual(rc["code"], "Security Quarantine Isolation")

            # Update
            res_upd = client.put(f"/api/v2/config/resolution-codes/{rc_id}", json={
                "description": "Updated quarantine notes"
            })
            self.assertEqual(res_upd.status_code, 200)
            self.assertEqual(res_upd.json()["description"], "Updated quarantine notes")

            # Delete
            res_del = client.delete(f"/api/v2/config/resolution-codes/{rc_id}")
            self.assertEqual(res_del.status_code, 200)

        def test_05_technicians_and_billing_rates(self):
            res = client.post("/api/v2/config/technicians", json={
                "name": "Nadia Vance",
                "email": "nadia.v@opennow.io",
                "hourly_rate": 125.0,
                "support_group": "Platform Architecture",
                "role": "Chief Enterprise Architect"
            })
            self.assertEqual(res.status_code, 201)
            tech = res.json()
            tech_id = tech["id"]

            # Rate lookup
            rate = config_engine.get_technician_rate("nadia.v@opennow.io")
            self.assertEqual(rate, 125.0)

            # Update rate
            client.put(f"/api/v2/config/technicians/{tech_id}", json={"hourly_rate": 135.0})
            self.assertEqual(config_engine.get_technician_rate("Nadia Vance"), 135.0)

            # Delete
            client.delete(f"/api/v2/config/technicians/{tech_id}")

        def test_06_business_rules_dynamic_evaluation(self):
            # Create a rule: tickets with "SAP" in title route to "SAP Basis Operations"
            res = client.post("/api/v2/config/business-rules", json={
                "name": "SAP Basis Urgent Routing",
                "order_num": 5,
                "criteria": {"field": "title", "operator": "contains", "value": "SAP"},
                "actions": {"assignment_group": "SAP Basis Operations", "priority": "P2"}
            })
            self.assertEqual(res.status_code, 201)
            rule = res.json()
            rule_id = rule["id"]

            # Evaluate ticket payload
            test_ticket = {
                "title": "SAP Hana memory limit exceeded in production",
                "category": "Enterprise Applications",
                "impact": "2 - Medium",
                "urgency": "2 - Medium"
            }
            evaluated, applied = config_engine.evaluate_business_rules(test_ticket)
            self.assertEqual(evaluated["assignment_group"], "SAP Basis Operations")
            self.assertEqual(evaluated["priority"], "P2")
            self.assertTrue(any("SAP_BASIS_URGENT_ROUTING" in r for r in applied))

            # Cleanup
            client.delete(f"/api/v2/config/business-rules/{rule_id}")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMasterDataConfigEngine)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    if not res.wasSuccessful():
        import sys
        sys.exit(1)
