"""OpenNow Incident Management Core Engine
========================================
Reverse-engineered architecture combining Zoho ServiceDesk Plus, GLPI, and iTop
best-practice ITSM standards.

Components:
1. Three-Tier Taxonomy (Category -> Subcategory -> Item) with pre-seeded trees
   (Hardware, Software, Network, Database, ERP, IT Services).
2. Dynamic Priority Matrix (Impact x Urgency -> Priority P1-P4) with configurable rules.
3. Incident Lifecycle State Machine (Draft -> Submitted -> Assigned -> In_Progress ->
   Pending_Customer -> Pending_Vendor -> Resolved -> Closed -> Cancelled) with transition guards.
4. Pauseable SLA Engine with business hours support and automatic pause/resume on Pending_* states.
5. Technician Worklogs & Labor Cost Tracking with billable/non-billable hours & rates.
6. Incident Subtasks with sequence ordering and resolution block on open critical tasks.
7. Business Rules Engine for automated evaluation and actions on create/update.
8. SQLite Storage engine with WAL mode and foreign key integrity.
9. Comprehensive Unit Test Suite.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sqlite3
import sys
import unittest
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("opennow.incident_module")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# ============================================================================
# 0. EXCEPTIONS & ENUMS
# ============================================================================

class IncidentModuleError(Exception):
    """Base exception for all incident module operations."""
    pass


class InvalidStateTransitionError(IncidentModuleError):
    """Raised when an illegal lifecycle transition is attempted."""
    pass


class TransitionGuardError(IncidentModuleError):
    """Raised when transition guard conditions (e.g. required fields, subtasks) fail."""
    pass


class TaxonomyValidationError(IncidentModuleError):
    """Raised when category, subcategory, or item hierarchy validation fails."""
    pass


class BusinessRuleError(IncidentModuleError):
    """Raised when a business rule fails evaluation or execution."""
    pass


class SubtaskError(IncidentModuleError):
    """Raised when subtask ordering or critical checks fail."""
    pass


class IncidentState(str, Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In_Progress"
    PENDING_CUSTOMER = "Pending_Customer"
    PENDING_VENDOR = "Pending_Vendor"
    RESOLVED = "Resolved"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"


class ImpactLevel(int, Enum):
    ENTERPRISE = 1      # 1 - Enterprise (Organization wide)
    DEPARTMENT = 2      # 2 - Department (Multiple users/group)
    USER = 3            # 3 - Single User


class UrgencyLevel(int, Enum):
    CRITICAL = 1        # 1 - Critical (Work completely halted)
    HIGH = 2            # 2 - High (Severe degradation)
    MEDIUM = 3          # 3 - Medium (Moderate disruption, workaround exists)
    LOW = 4             # 4 - Low (Minor inconvenience/informational)


class PriorityLevel(str, Enum):
    P1 = "P1"           # Critical
    P2 = "P2"           # High
    P3 = "P3"           # Medium
    P4 = "P4"           # Low


class SubtaskStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In_Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class SLAStatus(str, Enum):
    NOT_STARTED = "Not_Started"
    RUNNING = "Running"
    PAUSED = "Paused"
    ACHIEVED = "Achieved"
    BREACHED = "Breached"


# Standard ISO Datetime helper
def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

def to_iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()

def from_iso(s: Optional[str]) -> Optional[datetime.datetime]:
    if not s:
        return None
    try:
        # Python 3.11+ supports fromisoformat with Z or timezone
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


# ============================================================================
# 1. THREE-TIER TAXONOMY PRE-SEEDED DATA
# ============================================================================

TAXONOMY_SEEDS = [
    {
        "code": "HARDWARE",
        "name": "Hardware",
        "description": "Physical workstations, server blades, mobile devices, and peripherals",
        "subcategories": [
            {
                "code": "LAPTOP_DESKTOP",
                "name": "Laptop & Desktop",
                "description": "Standard user endpoints and workstation hardware",
                "items": [
                    {"code": "SCREEN_DISPLAY", "name": "Screen / Display Defect", "description": "Flickering, broken LCD, black screen"},
                    {"code": "KEYBOARD_TOUCHPAD", "name": "Keyboard & Touchpad", "description": "Unresponsive keys, trackpad failure"},
                    {"code": "MOTHERBOARD", "name": "Motherboard / Logic Board", "description": "Power-on self-test failure, board short"},
                    {"code": "POWER_BATTERY", "name": "Power Adapter & Battery", "description": "Battery swollen, no charge, faulty adapter"},
                    {"code": "DOCKING_STATION", "name": "Thunderbolt / USB-C Dock", "description": "Monitor output drop, USB disconnection"},
                    {"code": "RAM_STORAGE", "name": "Memory & NVMe SSD", "description": "SMART failure, bad sectors, memory errors"},
                ],
            },
            {
                "code": "SERVER_INFRA",
                "name": "Server Infrastructure",
                "description": "Rack servers, blade enclosures, and chassis components",
                "items": [
                    {"code": "RAID_CONTROLLER", "name": "RAID Controller / Array", "description": "Degraded virtual disk, controller cache battery"},
                    {"code": "SERVER_PSU", "name": "Redundant PSU Failure", "description": "Power supply unit offline or faulted"},
                    {"code": "THERMAL_COOLING", "name": "Chassis Thermal & Fans", "description": "High temp sensor alert, fan tachometer failure"},
                    {"code": "IPMI_BMC", "name": "iDRAC / iLO BMC Controller", "description": "Out-of-band management unresponsive"},
                ],
            },
            {
                "code": "PERIPHERALS",
                "name": "Peripherals & Audio/Video",
                "description": "Printers, conference room displays, external webcams",
                "items": [
                    {"code": "NETWORK_PRINTER", "name": "Multi-Function Office Printer", "description": "Paper jam, toner error, offline spooler"},
                    {"code": "CONFERENCE_AV", "name": "Room VC & Microphone Bar", "description": "HDMI capture card fault, mic echo"},
                    {"code": "BARCODE_SCANNER", "name": "Warehouse Barcode Scanner", "description": "Handheld terminal scanning laser fail"},
                ],
            },
            {
                "code": "MOBILE_DEVICE",
                "name": "Mobile Devices",
                "description": "Corporate smartphones, rugged tablets, and cellular hotspots",
                "items": [
                    {"code": "CORP_PHONE", "name": "Corporate Smartphone", "description": "Cellular radio failure, cracked digitizer"},
                    {"code": "RUGGED_TABLET", "name": "Rugged Field Tablet", "description": "IP67 housing crack, battery failure"},
                ],
            },
        ],
    },
    {
        "code": "SOFTWARE",
        "name": "Software",
        "description": "Operating systems, office suites, engineering tools, and client applications",
        "subcategories": [
            {
                "code": "OPERATING_SYSTEM",
                "name": "Operating System",
                "description": "Windows, macOS, Linux distributions",
                "items": [
                    {"code": "OS_CRASH_BSOD", "name": "Kernel Panic / BSOD", "description": "Blue screen of death or kernel dump"},
                    {"code": "PATCH_CORRUPTION", "name": "OS Patch & Windows Update", "description": "Update loop, rollback error"},
                    {"code": "CORRUPT_PROFILE", "name": "User Profile Corruption", "description": "Temporary profile loaded, registry hive lock"},
                ],
            },
            {
                "code": "PRODUCTIVITY_SUITE",
                "name": "Productivity Suite",
                "description": "Microsoft 365, Google Workspace, Adobe Creative Cloud",
                "items": [
                    {"code": "M365_ACTIVATION", "name": "Office 365 License Activation", "description": "Account unlicensed or token expired"},
                    {"code": "OUTLOOK_SYNC", "name": "Outlook OST / Profile Sync", "description": "Stuck in disconnected, OST corruption"},
                    {"code": "SPREADSHEET_MACRO", "name": "Excel Add-in / Macro Crash", "description": "VBA module error or COM addin crash"},
                ],
            },
            {
                "code": "COLLABORATION_TOOL",
                "name": "Collaboration & Messaging",
                "description": "Teams, Slack, Zoom client applications",
                "items": [
                    {"code": "TEAMS_CALLING", "name": "Teams / Slack Voice Drop", "description": "Audio call dropped, SIP trunk error"},
                    {"code": "SCREEN_SHARE_FAIL", "name": "Screen Sharing Permission", "description": "Wayland / macOS screen recording permission"},
                ],
            },
            {
                "code": "DEV_TOOLS",
                "name": "Developer & Engineering Tools",
                "description": "IDEs, Docker Desktop, Git, Compilers",
                "items": [
                    {"code": "DOCKER_WSL", "name": "Docker Desktop WSL2 Backend", "description": "Daemon not responding, pipe broken"},
                    {"code": "GIT_CREDENTIAL", "name": "Git SSH / GPG Key Failure", "description": "Permission denied (publickey)"},
                ],
            },
        ],
    },
    {
        "code": "NETWORK",
        "name": "Network",
        "description": "LAN switching, WAN links, VPN, Firewalls, DNS, and DHCP",
        "subcategories": [
            {
                "code": "LAN_WLAN",
                "name": "Local & Wireless Network",
                "description": "Access switches, 802.1X, Wi-Fi APs",
                "items": [
                    {"code": "SWITCH_PORT_ERROR", "name": "Switch Port Err-Disabled", "description": "BPDU guard, storm control tripped"},
                    {"code": "WIFI_AUTH_FAILURE", "name": "Enterprise Wi-Fi 802.1X", "description": "Radius cert expired, EAP TLS fail"},
                    {"code": "VLAN_MISMATCH", "name": "VLAN / Trunk Configuration", "description": "Native VLAN mismatch, dropped packets"},
                ],
            },
            {
                "code": "WAN_ROUTING",
                "name": "WAN & SD-WAN",
                "description": "MPLS, Internet DIA, BGP peering, SD-WAN tunnels",
                "items": [
                    {"code": "FIBER_CUT", "name": "Primary DIA Circuit Down", "description": "Carrier loss of signal (LOS)"},
                    {"code": "BGP_NEIGHBOR_FLAP", "name": "BGP Session Flapping", "description": "Hold timer expired, route flapping"},
                    {"code": "IPSEC_TUNNEL_DOWN", "name": "Site-to-Site IPsec VPN", "description": "IKE Phase 1/Phase 2 proposal mismatch"},
                ],
            },
            {
                "code": "FIREWALL_SECURITY",
                "name": "Firewall & Security Perimeter",
                "description": "Next-Gen Firewalls, Remote Access VPN, WAF",
                "items": [
                    {"code": "REMOTE_VPN_FAIL", "name": "GlobalProtect / AnyConnect Client", "description": "SAML gateway timeout, gateway down"},
                    {"code": "POLICY_BLOCKING", "name": "Firewall Security Policy Block", "description": "Legitimate traffic false positive block"},
                ],
            },
            {
                "code": "CORE_SERVICES",
                "name": "Core IP Services (DDI)",
                "description": "DNS resolution, DHCP scopes, NTP",
                "items": [
                    {"code": "DHCP_EXHAUSTION", "name": "DHCP Scope Pool Exhausted", "description": "No free IP address in subnet lease"},
                    {"code": "DNS_RESOLUTION", "name": "Internal DNS Forwarding Fail", "description": "Root hints timeout, SERVFAIL"},
                ],
            },
        ],
    },
    {
        "code": "DATABASE",
        "name": "Database",
        "description": "Relational and NoSQL database management systems and clustering",
        "subcategories": [
            {
                "code": "POSTGRESQL",
                "name": "PostgreSQL",
                "description": "PostgreSQL cluster, patroni, replication",
                "items": [
                    {"code": "PG_CONN_EXHAUSTED", "name": "Connection Pool Exhaustion", "description": "max_connections reached, PgBouncer drop"},
                    {"code": "PG_REPLICATION_LAG", "name": "Streaming Replication Lag", "description": "WAL sender lag exceeding threshold"},
                    {"code": "PG_TRANSACTION_ID", "name": "TXID Wraparound Risk", "description": "Autovacuum unable to catch up"},
                    {"code": "PG_DEADLOCK", "name": "Deadlock Detected Alert", "description": "Process detected deadlock on row locks"},
                ],
            },
            {
                "code": "ORACLE_DB",
                "name": "Oracle Database",
                "description": "Oracle RAC, Data Guard, ASM",
                "items": [
                    {"code": "ORA_TABLESPACE_FULL", "name": "Tablespace Full (ORA-01653)", "description": "Cannot extend table in tablespace"},
                    {"code": "ORA_ARCHIVELOG_FULL", "name": "Archivelog Destination Full", "description": "Database hung, archiver stuck"},
                    {"code": "ORA_DATAGUARD_GAP", "name": "Data Guard Transport Gap", "description": "Standby database fallen behind"},
                ],
            },
            {
                "code": "SQL_SERVER",
                "name": "Microsoft SQL Server",
                "description": "SQL Server AlwaysOn, TempDB, Agent jobs",
                "items": [
                    {"code": "MSSQL_TEMPDB_FULL", "name": "TempDB Storage Full", "description": "TempDB drive out of space"},
                    {"code": "MSSQL_AG_FAILOVER", "name": "AlwaysOn Failover / Unhealthy", "description": "Replica synchronization suspended"},
                ],
            },
            {
                "code": "MYSQL_MARIADB",
                "name": "MySQL & MariaDB",
                "description": "InnoDB engines, Galera clusters, Read replicas",
                "items": [
                    {"code": "MYSQL_TOO_MANY_CONN", "name": "Too Many Connections Error", "description": "ER_CON_COUNT_ERROR 1040"},
                    {"code": "MYSQL_GALERA_DESYNC", "name": "Galera Cluster Node Desync", "description": "Node in non-primary state"},
                ],
            },
        ],
    },
    {
        "code": "ERP",
        "name": "ERP & Business Systems",
        "description": "Enterprise Resource Planning, CRM, HCM, Billing engines",
        "subcategories": [
            {
                "code": "SAP_ERP",
                "name": "SAP S/4HANA",
                "description": "SAP core modules, Fiori, IDoc processing, RFC",
                "items": [
                    {"code": "SAP_IDOC_FAILED", "name": "IDoc Processing Failure", "description": "Status 51 application document not posted"},
                    {"code": "SAP_RFC_COMM_ERROR", "name": "RFC Gateway Connection Refused", "description": "RFC communication failure in SM59"},
                    {"code": "SAP_BATCH_ABORTED", "name": "Month-End Batch Job Cancelled", "description": "Job terminated with ABAP runtime error"},
                    {"code": "SAP_FIORI_SSO", "name": "Fiori Launchpad SAML Token", "description": "HTTP 500 or certificate validation failure"},
                ],
            },
            {
                "code": "WORKDAY_HCM",
                "name": "Workday HCM",
                "description": "Human Capital Management, payroll, onboarding",
                "items": [
                    {"code": "WD_PAYROLL_SYNC", "name": "Payroll EIB Integration Failed", "description": "Enterprise Interface Builder validation errors"},
                    {"code": "WD_ONBOARDING_STUCK", "name": "New Hire Onboarding BP Stuck", "description": "Business process waiting on orphaned step"},
                ],
            },
            {
                "code": "NETSUITE",
                "name": "Oracle NetSuite",
                "description": "Cloud ERP, SuiteScript, Order to Cash",
                "items": [
                    {"code": "NS_SUITESCRIPT_ERR", "name": "SuiteScript Governance Limit", "description": "SSS_USAGE_LIMIT_EXCEEDED in user event script"},
                    {"code": "NS_INVOICE_SYNC", "name": "Billing Schedule Sync Failure", "description": "Cannot generate billing schedule"},
                ],
            },
            {
                "code": "SALESFORCE_CRM",
                "name": "Salesforce CRM",
                "description": "Sales Cloud, Service Cloud, Apex Triggers",
                "items": [
                    {"code": "SF_APEX_LIMIT", "name": "Apex CPU Time Limit Exceeded", "description": "System.LimitException: Apex CPU time limit exceeded"},
                    {"code": "SF_INTEGRATION_SYNC", "name": "Outbound Message Timeout", "description": "Webhook endpoint failed to respond"},
                ],
            },
        ],
    },
    {
        "code": "IT_SERVICES",
        "name": "IT Enterprise Services",
        "description": "Identity, Cloud Infrastructure, Email, Backup & Disaster Recovery",
        "subcategories": [
            {
                "code": "IDENTITY_ACCESS",
                "name": "Identity & Access Management",
                "description": "Active Directory, Okta, Microsoft Entra ID, PAM",
                "items": [
                    {"code": "ACCOUNT_LOCKOUT", "name": "Privileged Account Lockout", "description": "Repeated bad password attempts across servers"},
                    {"code": "MFA_TOKEN_DESYNC", "name": "MFA Hardware/App Token Desync", "description": "TOTP drift or push notification delivery failure"},
                    {"code": "SAML_ASSERTION_FAIL", "name": "Federated SSO SAML Assertion", "description": "Audience restriction or clock skew mismatch"},
                ],
            },
            {
                "code": "CLOUD_INFRA",
                "name": "Cloud Infrastructure (AWS/Azure/GCP)",
                "description": "Compute instances, Kubernetes clusters, Object storage",
                "items": [
                    {"code": "K8S_CRASHLOOP", "name": "Kubernetes Pod CrashLoopBackOff", "description": "Application container failing liveness probe"},
                    {"code": "VM_UNREACHABLE", "name": "Cloud VM Instance Unreachable", "description": "Failed hypervisor health check or bad security group"},
                    {"code": "STORAGE_QUOTA_FULL", "name": "Cloud Storage Quota Reached", "description": "S3 / Blob storage capacity or write rate exceeded"},
                ],
            },
            {
                "code": "EMAIL_MESSAGING",
                "name": "Email & Messaging Services",
                "description": "Exchange Online, SMTP relays, mail security",
                "items": [
                    {"code": "MAIL_QUEUE_BACKLOG", "name": "Outbound SMTP Queue Backlog", "description": "Mail relay throttled or IP blocklisted"},
                    {"code": "MAILBOX_QUOTA", "name": "Executive Mailbox Quota Full", "description": "User cannot send or receive new emails"},
                ],
            },
            {
                "code": "BACKUP_RECOVERY",
                "name": "Backup & Disaster Recovery",
                "description": "Veeam, Commvault, Snapshot policies, Tape archives",
                "items": [
                    {"code": "DAILY_BACKUP_FAIL", "name": "Nightly Production Backup Failed", "description": "VSS snapshot creation failure or storage timeout"},
                    {"code": "SNAPSHOT_LOCK_ERR", "name": "Immutable Snapshot Lock Error", "description": "Object lock governance retention conflict"},
                ],
            },
        ],
    },
]


# ============================================================================
# 2. DYNAMIC PRIORITY MATRIX
# ============================================================================

class DynamicPriorityMatrix:
    """Configurable ITIL dynamic priority matrix calculator.
    
    Evaluates Impact (1-Enterprise, 2-Department, 3-Single User)
    against Urgency (1-Critical, 2-High, 3-Medium, 4-Low)
    to yield Priority (P1, P2, P3, P4).
    """

    DEFAULT_MATRIX: Dict[Tuple[int, int], str] = {
        # Impact 1: Enterprise
        (1, 1): PriorityLevel.P1.value,
        (1, 2): PriorityLevel.P1.value,
        (1, 3): PriorityLevel.P2.value,
        (1, 4): PriorityLevel.P3.value,
        # Impact 2: Department
        (2, 1): PriorityLevel.P2.value,
        (2, 2): PriorityLevel.P2.value,
        (2, 3): PriorityLevel.P3.value,
        (2, 4): PriorityLevel.P4.value,
        # Impact 3: Single User
        (3, 1): PriorityLevel.P3.value,
        (3, 2): PriorityLevel.P3.value,
        (3, 3): PriorityLevel.P4.value,
        (3, 4): PriorityLevel.P4.value,
    }

    def __init__(self, overrides: Optional[Dict[Tuple[int, int], str]] = None):
        self._matrix = dict(self.DEFAULT_MATRIX)
        if overrides:
            for k, v in overrides.items():
                self.set_rule(k[0], k[1], v)

    @staticmethod
    def normalize_impact(val: Union[int, str, ImpactLevel]) -> int:
        if isinstance(val, ImpactLevel):
            return val.value
        if isinstance(val, int):
            if val in (1, 2, 3):
                return val
            raise ValueError(f"Invalid impact level integer: {val}. Must be 1, 2, or 3.")
        val_str = str(val).strip().lower()
        if "1" in val_str or "enterprise" in val_str or "org" in val_str:
            return 1
        if "2" in val_str or "dept" in val_str or "department" in val_str:
            return 2
        if "3" in val_str or "user" in val_str or "single" in val_str:
            return 3
        raise ValueError(f"Cannot parse Impact value '{val}'. Supported: 1 (Enterprise), 2 (Department), 3 (User).")

    @staticmethod
    def normalize_urgency(val: Union[int, str, UrgencyLevel]) -> int:
        if isinstance(val, UrgencyLevel):
            return val.value
        if isinstance(val, int):
            if val in (1, 2, 3, 4):
                return val
            raise ValueError(f"Invalid urgency level integer: {val}. Must be 1, 2, 3, or 4.")
        val_str = str(val).strip().lower()
        if "1" in val_str or "crit" in val_str:
            return 1
        if "2" in val_str or "high" in val_str:
            return 2
        if "3" in val_str or "med" in val_str:
            return 3
        if "4" in val_str or "low" in val_str:
            return 4
        raise ValueError(f"Cannot parse Urgency value '{val}'. Supported: 1 (Critical), 2 (High), 3 (Medium), 4 (Low).")

    def set_rule(self, impact: Union[int, str], urgency: Union[int, str], priority: str) -> None:
        imp_norm = self.normalize_impact(impact)
        urg_norm = self.normalize_urgency(urgency)
        prio_norm = str(priority).strip().upper()
        if prio_norm not in ("P1", "P2", "P3", "P4"):
            raise ValueError(f"Invalid priority '{priority}'. Must be P1, P2, P3, or P4.")
        self._matrix[(imp_norm, urg_norm)] = prio_norm

    def calculate_priority(self, impact: Union[int, str, ImpactLevel], urgency: Union[int, str, UrgencyLevel]) -> str:
        imp_norm = self.normalize_impact(impact)
        urg_norm = self.normalize_urgency(urgency)
        return self._matrix.get((imp_norm, urg_norm), PriorityLevel.P3.value)

    def get_full_matrix(self) -> Dict[str, str]:
        """Returns string key representation e.g. '1x1': 'P1'."""
        return {f"{imp}x{urg}": prio for (imp, urg), prio in sorted(self._matrix.items())}


# ============================================================================
# 3. INCIDENT LIFECYCLE STATE MACHINE & TRANSITION GUARDS
# ============================================================================

class IncidentStateMachine:
    """Enforces allowed lifecycle transitions and strict ITSM guards."""

    ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        IncidentState.DRAFT.value: {
            IncidentState.SUBMITTED.value,
            IncidentState.CANCELLED.value,
        },
        IncidentState.SUBMITTED.value: {
            IncidentState.ASSIGNED.value,
            IncidentState.IN_PROGRESS.value,
            IncidentState.CANCELLED.value,
        },
        IncidentState.ASSIGNED.value: {
            IncidentState.IN_PROGRESS.value,
            IncidentState.PENDING_CUSTOMER.value,
            IncidentState.PENDING_VENDOR.value,
            IncidentState.CANCELLED.value,
        },
        IncidentState.IN_PROGRESS.value: {
            IncidentState.ASSIGNED.value,
            IncidentState.PENDING_CUSTOMER.value,
            IncidentState.PENDING_VENDOR.value,
            IncidentState.RESOLVED.value,
            IncidentState.CANCELLED.value,
        },
        IncidentState.PENDING_CUSTOMER.value: {
            IncidentState.IN_PROGRESS.value,
            IncidentState.RESOLVED.value,
            IncidentState.CANCELLED.value,
        },
        IncidentState.PENDING_VENDOR.value: {
            IncidentState.IN_PROGRESS.value,
            IncidentState.RESOLVED.value,
            IncidentState.CANCELLED.value,
        },
        IncidentState.RESOLVED.value: {
            IncidentState.CLOSED.value,
            IncidentState.IN_PROGRESS.value,  # Reopened
            IncidentState.CANCELLED.value,
        },
        IncidentState.CLOSED.value: {
            IncidentState.IN_PROGRESS.value,  # Reopened under strict exception
        },
        IncidentState.CANCELLED.value: set(), # Terminal state
    }

    @classmethod
    def is_transition_allowed(cls, from_state: str, to_state: str) -> bool:
        allowed = cls.ALLOWED_TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @classmethod
    def validate_transition(
        cls,
        from_state: str,
        to_state: str,
        incident_data: Dict[str, Any],
        open_critical_subtasks: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Validates that transition is legal and all guards are satisfied.
        
        Raises:
            InvalidStateTransitionError: If the transition path is not permitted.
            TransitionGuardError: If required guard parameters are missing or incomplete.
        """
        if from_state == to_state:
            return  # No-op

        if not cls.is_transition_allowed(from_state, to_state):
            allowed_list = sorted(list(cls.ALLOWED_TRANSITIONS.get(from_state, [])))
            raise InvalidStateTransitionError(
                f"Illegal state transition from '{from_state}' to '{to_state}'. "
                f"Permitted next states: {allowed_list}"
            )

        # Guard 1: Transitioning to RESOLVED requires resolution_code, root_cause, resolution_notes
        if to_state == IncidentState.RESOLVED.value:
            missing = []
            res_code = str(incident_data.get("resolution_code") or "").strip()
            root_cause = str(incident_data.get("root_cause") or "").strip()
            res_notes = str(incident_data.get("resolution_notes") or "").strip()

            if not res_code:
                missing.append("resolution_code")
            if not root_cause:
                missing.append("root_cause")
            if not res_notes:
                missing.append("resolution_notes")

            if missing:
                raise TransitionGuardError(
                    f"Cannot resolve incident {incident_data.get('incident_number', '')}: "
                    f"Missing required resolution fields: {', '.join(missing)}."
                )

            # Subtask Guard: Incident cannot be resolved if any critical subtask is not completed/cancelled
            if open_critical_subtasks:
                task_summaries = [
                    f"#{t.get('id')} '{t.get('title')}' (Status: {t.get('status')})"
                    for t in open_critical_subtasks
                ]
                raise TransitionGuardError(
                    f"Cannot resolve incident {incident_data.get('incident_number', '')}: "
                    f"Blocking resolution because {len(open_critical_subtasks)} critical subtask(s) are incomplete: "
                    + "; ".join(task_summaries)
                )

        # Guard 2: Transitioning to PENDING_CUSTOMER or PENDING_VENDOR requires pause_reason
        if to_state in (IncidentState.PENDING_CUSTOMER.value, IncidentState.PENDING_VENDOR.value):
            pause_reason = str(incident_data.get("pause_reason") or "").strip()
            if not pause_reason:
                raise TransitionGuardError(
                    f"Cannot transition incident {incident_data.get('incident_number', '')} to '{to_state}': "
                    f"A valid non-empty 'pause_reason' must be provided."
                )

        # Guard 3: Transitioning to ASSIGNED requires assigned_to or assignment_group
        if to_state == IncidentState.ASSIGNED.value:
            assigned_to = str(incident_data.get("assigned_to") or "").strip()
            assignment_group = str(incident_data.get("assignment_group") or "").strip()
            if not assigned_to and not assignment_group:
                raise TransitionGuardError(
                    f"Cannot transition incident {incident_data.get('incident_number', '')} to 'Assigned': "
                    f"Either 'assigned_to' technician or 'assignment_group' must be designated."
                )

        # Guard 4: Transitioning to CANCELLED requires cancellation_reason
        if to_state == IncidentState.CANCELLED.value:
            cancellation_reason = str(incident_data.get("cancellation_reason") or "").strip()
            if not cancellation_reason:
                raise TransitionGuardError(
                    f"Cannot cancel incident {incident_data.get('incident_number', '')}: "
                    f"A valid non-empty 'cancellation_reason' is required."
                )


# ============================================================================
# 4. PAUSEABLE SLA ENGINE
# ============================================================================

@dataclass
class SLAPolicy:
    priority: str
    response_seconds: int
    resolution_seconds: int
    business_hours_only: bool = False
    schedule_start_hour: int = 9   # 09:00
    schedule_end_hour: int = 17    # 17:00
    workdays: Tuple[int, ...] = (0, 1, 2, 3, 4)  # Mon-Fri (0=Mon, 6=Sun)


class PauseableSLAEngine:
    """Production SLA Engine supporting 24x7 and Business Hours operational calendars,
    with clock pausing on Pending_Customer / Pending_Vendor states.
    """

    DEFAULT_POLICIES: Dict[str, SLAPolicy] = {
        PriorityLevel.P1.value: SLAPolicy(
            priority="P1",
            response_seconds=15 * 60,      # 15 minutes
            resolution_seconds=2 * 3600,   # 2 hours
            business_hours_only=False,     # 24x7
        ),
        PriorityLevel.P2.value: SLAPolicy(
            priority="P2",
            response_seconds=30 * 60,      # 30 minutes
            resolution_seconds=4 * 3600,   # 4 hours
            business_hours_only=False,     # 24x7
        ),
        PriorityLevel.P3.value: SLAPolicy(
            priority="P3",
            response_seconds=2 * 3600,     # 2 hours
            resolution_seconds=8 * 3600,   # 8 operational hours (1 business day)
            business_hours_only=True,
        ),
        PriorityLevel.P4.value: SLAPolicy(
            priority="P4",
            response_seconds=4 * 3600,     # 4 hours
            resolution_seconds=24 * 3600,  # 24 operational hours (3 business days)
            business_hours_only=True,
        ),
    }

    def __init__(self, policies: Optional[Dict[str, SLAPolicy]] = None):
        self.policies = policies or dict(self.DEFAULT_POLICIES)

    def get_policy(self, priority: str) -> SLAPolicy:
        p = str(priority).strip().upper()
        if p not in self.policies:
            p = PriorityLevel.P3.value
        return self.policies[p]

    def add_operational_seconds(
        self, start_dt: datetime.datetime, seconds_to_add: int, policy: SLAPolicy
    ) -> datetime.datetime:
        """Adds operational seconds to start_dt, stepping through business hours if applicable."""
        if not policy.business_hours_only:
            return start_dt + datetime.timedelta(seconds=seconds_to_add)

        current = start_dt
        remaining_seconds = seconds_to_add

        # Advance minute by minute or in daily blocks for efficiency
        while remaining_seconds > 0:
            # Check if current day is a workday
            if current.weekday() not in policy.workdays:
                # Advance to next day at schedule_start_hour
                current = (current + datetime.timedelta(days=1)).replace(
                    hour=policy.schedule_start_hour, minute=0, second=0, microsecond=0
                )
                continue

            # Before business hours
            if current.hour < policy.schedule_start_hour:
                current = current.replace(hour=policy.schedule_start_hour, minute=0, second=0, microsecond=0)

            # After business hours
            if current.hour >= policy.schedule_end_hour:
                current = (current + datetime.timedelta(days=1)).replace(
                    hour=policy.schedule_start_hour, minute=0, second=0, microsecond=0
                )
                continue

            # Within business hours on a workday
            end_of_business_today = current.replace(
                hour=policy.schedule_end_hour, minute=0, second=0, microsecond=0
            )
            seconds_left_today = int((end_of_business_today - current).total_seconds())

            if remaining_seconds <= seconds_left_today:
                current = current + datetime.timedelta(seconds=remaining_seconds)
                remaining_seconds = 0
            else:
                remaining_seconds -= seconds_left_today
                # Jump to start of next day
                current = (current + datetime.timedelta(days=1)).replace(
                    hour=policy.schedule_start_hour, minute=0, second=0, microsecond=0
                )

        return current

    def calculate_initial_sla(
        self, priority: str, created_at: datetime.datetime
    ) -> Dict[str, Any]:
        """Calculates SLA targets and initial due timestamps."""
        policy = self.get_policy(priority)
        response_due = self.add_operational_seconds(created_at, policy.response_seconds, policy)
        resolution_due = self.add_operational_seconds(created_at, policy.resolution_seconds, policy)

        return {
            "response_sla_target_seconds": policy.response_seconds,
            "resolution_sla_target_seconds": policy.resolution_seconds,
            "response_sla_due": to_iso(response_due),
            "resolution_sla_due": to_iso(resolution_due),
        }

    def process_state_pause_resume(
        self,
        from_state: str,
        to_state: str,
        incident_dict: Dict[str, Any],
        event_time: datetime.datetime,
    ) -> Dict[str, Any]:
        """Handles pause initiation or resumption, adjusting SLA deadlines accordingly."""
        updates: Dict[str, Any] = {}
        paused_states = {IncidentState.PENDING_CUSTOMER.value, IncidentState.PENDING_VENDOR.value}

        # 1. Entering Paused State
        if to_state in paused_states and from_state not in paused_states:
            updates["is_paused"] = 1
            updates["paused_at"] = to_iso(event_time)

        # 2. Resuming from Paused State to Active State
        elif from_state in paused_states and to_state not in paused_states:
            paused_at_iso = incident_dict.get("paused_at")
            paused_at_dt = from_iso(paused_at_iso)
            if paused_at_dt:
                pause_delta = max(0, int((event_time - paused_at_dt).total_seconds()))
                current_total = int(incident_dict.get("total_paused_seconds") or 0)
                new_total_paused = current_total + pause_delta
                updates["total_paused_seconds"] = new_total_paused
                updates["is_paused"] = 0
                updates["paused_at"] = None

                # Adjust Due Dates for remaining SLA
                policy = self.get_policy(incident_dict.get("priority", "P3"))
                
                # Adjust response SLA due date if not yet responded
                if not incident_dict.get("first_responded_at") and incident_dict.get("response_sla_due"):
                    old_resp_due = from_iso(incident_dict.get("response_sla_due"))
                    if old_resp_due:
                        new_resp_due = self.add_operational_seconds(old_resp_due, pause_delta, policy)
                        updates["response_sla_due"] = to_iso(new_resp_due)

                # Adjust resolution SLA due date if not yet resolved
                if not incident_dict.get("resolved_at") and incident_dict.get("resolution_sla_due"):
                    old_res_due = from_iso(incident_dict.get("resolution_sla_due"))
                    if old_res_due:
                        new_res_due = self.add_operational_seconds(old_res_due, pause_delta, policy)
                        updates["resolution_sla_due"] = to_iso(new_res_due)
            else:
                updates["is_paused"] = 0
                updates["paused_at"] = None

        return updates

    def compute_sla_metrics(
        self, incident: Dict[str, Any], current_time: Optional[datetime.datetime] = None
    ) -> Dict[str, Any]:
        """Calculates SLA operational metrics (elapsed, remaining, status)."""
        now = current_time or now_utc()
        created_at = from_iso(incident.get("created_at")) or now
        response_due = from_iso(incident.get("response_sla_due"))
        resolution_due = from_iso(incident.get("resolution_sla_due"))
        first_responded_at = from_iso(incident.get("first_responded_at"))
        resolved_at = from_iso(incident.get("resolved_at"))
        is_paused = bool(incident.get("is_paused", 0))

        # Response SLA Status
        if first_responded_at:
            if response_due and first_responded_at <= response_due:
                response_status = SLAStatus.ACHIEVED.value
            else:
                response_status = SLAStatus.BREACHED.value
            response_remaining_seconds = 0
        elif is_paused:
            response_status = SLAStatus.PAUSED.value
            response_remaining_seconds = int((response_due - now).total_seconds()) if response_due else 0
        else:
            if response_due and now > response_due:
                response_status = SLAStatus.BREACHED.value
                response_remaining_seconds = int((response_due - now).total_seconds())
            else:
                response_status = SLAStatus.RUNNING.value
                response_remaining_seconds = max(0, int((response_due - now).total_seconds())) if response_due else 0

        # Resolution SLA Status
        if resolved_at:
            if resolution_due and resolved_at <= resolution_due:
                resolution_status = SLAStatus.ACHIEVED.value
            else:
                resolution_status = SLAStatus.BREACHED.value
            resolution_remaining_seconds = 0
        elif is_paused:
            resolution_status = SLAStatus.PAUSED.value
            resolution_remaining_seconds = int((resolution_due - now).total_seconds()) if resolution_due else 0
        else:
            if resolution_due and now > resolution_due:
                resolution_status = SLAStatus.BREACHED.value
                resolution_remaining_seconds = int((resolution_due - now).total_seconds())
            else:
                resolution_status = SLAStatus.RUNNING.value
                resolution_remaining_seconds = max(0, int((resolution_due - now).total_seconds())) if resolution_due else 0

        total_paused = int(incident.get("total_paused_seconds") or 0)
        # If currently paused, add current session pause time
        if is_paused and incident.get("paused_at"):
            p_start = from_iso(incident.get("paused_at"))
            if p_start:
                total_paused += max(0, int((now - p_start).total_seconds()))

        elapsed_wall_seconds = max(0, int((now - created_at).total_seconds()))
        net_operational_seconds = max(0, elapsed_wall_seconds - total_paused)

        return {
            "response_status": response_status,
            "response_remaining_seconds": response_remaining_seconds,
            "response_sla_due": to_iso(response_due),
            "resolution_status": resolution_status,
            "resolution_remaining_seconds": resolution_remaining_seconds,
            "resolution_sla_due": to_iso(resolution_due),
            "total_paused_seconds": total_paused,
            "net_operational_seconds": net_operational_seconds,
            "is_response_breached": response_status == SLAStatus.BREACHED.value,
            "is_resolution_breached": resolution_status == SLAStatus.BREACHED.value,
        }


# ============================================================================
# 5. BUSINESS RULES ENGINE
# ============================================================================

class BusinessRulesEngine:
    """Evaluates configurable business criteria against incident records
    and executes actions (assignment, escalation, prioritization, tagging).
    """

    @staticmethod
    def _evaluate_criterion(field_val: Any, operator: str, target_val: Any) -> bool:
        op = operator.lower().strip()
        str_val = str(field_val).lower().strip() if field_val is not None else ""
        
        if op == "eq":
            if isinstance(target_val, (int, float)) and isinstance(field_val, (int, float)):
                return field_val == target_val
            return str_val == str(target_val).lower().strip()
        elif op == "neq":
            if isinstance(target_val, (int, float)) and isinstance(field_val, (int, float)):
                return field_val != target_val
            return str_val != str(target_val).lower().strip()
        elif op == "contains":
            return str(target_val).lower().strip() in str_val
        elif op == "in":
            if isinstance(target_val, (list, tuple, set)):
                lowered_targets = [str(t).lower().strip() for t in target_val]
                return str_val in lowered_targets
            return str_val == str(target_val).lower().strip()
        elif op == "not_in":
            if isinstance(target_val, (list, tuple, set)):
                lowered_targets = [str(t).lower().strip() for t in target_val]
                return str_val not in lowered_targets
            return str_val != str(target_val).lower().strip()
        elif op in ("gt", "lt", "gte", "lte"):
            try:
                num_field = float(field_val)
                num_target = float(target_val)
                if op == "gt":
                    return num_field > num_target
                elif op == "lt":
                    return num_field < num_target
                elif op == "gte":
                    return num_field >= num_target
                elif op == "lte":
                    return num_field <= num_target
            except (ValueError, TypeError):
                return False
        elif op == "is_empty":
            return field_val is None or str_val == ""
        elif op == "is_not_empty":
            return field_val is not None and str_val != ""
        return False

    @classmethod
    def evaluate_rule(cls, rule: Dict[str, Any], incident_data: Dict[str, Any]) -> bool:
        """Evaluates whether incident_data meets the rule's criteria."""
        criteria = rule.get("criteria", [])
        if isinstance(criteria, str):
            try:
                criteria = json.loads(criteria)
            except Exception:
                return False

        if not criteria:
            return False

        match_condition = str(rule.get("match_condition", "ALL")).strip().upper()
        results = []

        for crit in criteria:
            field_name = crit.get("field")
            operator = crit.get("operator", "eq")
            expected_val = crit.get("value")
            actual_val = incident_data.get(field_name)

            matched = cls._evaluate_criterion(actual_val, operator, expected_val)
            results.append(matched)

        if match_condition == "ANY":
            return any(results)
        return all(results)

    @classmethod
    def apply_actions(
        cls, actions: Union[List[Dict[str, Any]], str], incident_data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Applies configured actions to incident_data.
        
        Returns:
            (updated_fields_dict, side_effect_actions_list)
        """
        if isinstance(actions, str):
            try:
                actions = json.loads(actions)
            except Exception:
                actions = []

        mutations: Dict[str, Any] = {}
        side_effects: List[Dict[str, Any]] = []

        for act in actions:
            action_type = act.get("action")
            if action_type == "set_field":
                f_name = act.get("field")
                f_val = act.get("value")
                if f_name:
                    mutations[f_name] = f_val
                    incident_data[f_name] = f_val
            elif action_type == "trigger_escalation":
                mutations["is_escalated"] = 1
                mutations["escalation_level"] = act.get("level", 1)
                incident_data["is_escalated"] = 1
                incident_data["escalation_level"] = act.get("level", 1)
                side_effects.append(act)
            elif action_type == "add_tag":
                tag = act.get("tag")
                if tag:
                    current_tags = incident_data.get("tags") or []
                    if isinstance(current_tags, str):
                        try:
                            current_tags = json.loads(current_tags)
                        except Exception:
                            current_tags = []
                    if tag not in current_tags:
                        current_tags.append(tag)
                        mutations["tags"] = json.dumps(current_tags)
                        incident_data["tags"] = current_tags
            elif action_type in ("add_subtask", "notify_webhook"):
                side_effects.append(act)

        return mutations, side_effects


DEFAULT_BUSINESS_RULES = [
    {
        "rule_name": "RULE_DB_CRITICAL_DBA_ESCALATION",
        "description": "Auto-assign Database Critical incidents to DBA-Team with P1 and immediate escalation.",
        "trigger_event": "CREATE",
        "execution_order": 1,
        "is_active": 1,
        "match_condition": "ALL",
        "criteria": [
            {"field": "category_name", "operator": "eq", "value": "Database"},
            {"field": "urgency", "operator": "in", "value": [1, "1", "Critical"]},
        ],
        "actions": [
            {"action": "set_field", "field": "assignment_group", "value": "DBA-Team"},
            {"action": "set_field", "field": "priority", "value": "P1"},
            {"action": "trigger_escalation", "level": 1, "reason": "Critical database tier impairment"},
            {"action": "add_tag", "tag": "DBA_HIGH_PRIORITY"},
        ],
    },
    {
        "rule_name": "RULE_ERP_ENTERPRISE_ROUTING",
        "description": "Auto-route Enterprise-wide ERP issues to Enterprise-Apps team with P1.",
        "trigger_event": "CREATE",
        "execution_order": 2,
        "is_active": 1,
        "match_condition": "ALL",
        "criteria": [
            {"field": "category_name", "operator": "eq", "value": "ERP & Business Systems"},
            {"field": "impact", "operator": "eq", "value": 1},
        ],
        "actions": [
            {"action": "set_field", "field": "assignment_group", "value": "Enterprise-Apps"},
            {"action": "set_field", "field": "priority", "value": "P1"},
            {"action": "trigger_escalation", "level": 1, "reason": "Enterprise ERP disruption"},
        ],
    },
    {
        "rule_name": "RULE_NETWORK_WAN_OUTAGE",
        "description": "Auto-route WAN fiber cut incidents directly to Network NOC team.",
        "trigger_event": "CREATE",
        "execution_order": 3,
        "is_active": 1,
        "match_condition": "ALL",
        "criteria": [
            {"field": "category_name", "operator": "eq", "value": "Network"},
            {"field": "subcategory_name", "operator": "contains", "value": "WAN"},
        ],
        "actions": [
            {"action": "set_field", "field": "assignment_group", "value": "Network-NOC"},
            {"action": "add_tag", "tag": "CIRCUIT_DISRUPTION"},
        ],
    },
    {
        "rule_name": "RULE_IAM_SERVICEDESK_L1",
        "description": "Direct single-user IAM issues to ServiceDesk-L1 queue.",
        "trigger_event": "CREATE",
        "execution_order": 4,
        "is_active": 1,
        "match_condition": "ALL",
        "criteria": [
            {"field": "subcategory_name", "operator": "contains", "value": "Identity"},
            {"field": "impact", "operator": "eq", "value": 3},
        ],
        "actions": [
            {"action": "set_field", "field": "assignment_group", "value": "ServiceDesk-L1"},
            {"action": "add_tag", "tag": "IAM_FAST_TRACK"},
        ],
    },
]


# ============================================================================
# 6. SQLITE STORAGE ENGINE & INCIDENT MODULE
# ============================================================================

class IncidentDatabase:
    """Manages SQLite schema, WAL mode, foreign keys, and transaction lifecycles."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._shared_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:", timeout=30.0, check_same_thread=False)
            self._shared_conn.row_factory = sqlite3.Row
            self._shared_conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        return conn

    def close(self) -> None:
        if self._shared_conn is not None:
            try:
                self._shared_conn.close()
            except Exception:
                pass
            self._shared_conn = None

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            # 1. Categories
            conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """)

            # 2. Subcategories
            conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_subcategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES incident_categories(id) ON DELETE CASCADE,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(category_id, code)
            );
            """)

            # 3. Items
            conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subcategory_id INTEGER NOT NULL REFERENCES incident_subcategories(id) ON DELETE CASCADE,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(subcategory_id, code)
            );
            """)

            # 4. Incidents
            conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_number TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category_id INTEGER REFERENCES incident_categories(id),
                subcategory_id INTEGER REFERENCES incident_subcategories(id),
                item_id INTEGER REFERENCES incident_items(id),
                impact INTEGER NOT NULL DEFAULT 3,
                urgency INTEGER NOT NULL DEFAULT 3,
                priority TEXT NOT NULL DEFAULT 'P3',
                state TEXT NOT NULL DEFAULT 'Draft',
                caller_name TEXT,
                caller_email TEXT,
                assigned_to TEXT,
                assignment_group TEXT,
                resolution_code TEXT,
                root_cause TEXT,
                resolution_notes TEXT,
                pause_reason TEXT,
                cancellation_reason TEXT,
                is_paused INTEGER NOT NULL DEFAULT 0,
                paused_at TEXT,
                total_paused_seconds INTEGER NOT NULL DEFAULT 0,
                response_sla_target_seconds INTEGER NOT NULL,
                resolution_sla_target_seconds INTEGER NOT NULL,
                response_sla_due TEXT,
                resolution_sla_due TEXT,
                first_responded_at TEXT,
                resolved_at TEXT,
                closed_at TEXT,
                escalation_level INTEGER NOT NULL DEFAULT 0,
                is_escalated INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]',
                custom_fields TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 5. Worklogs
            conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_worklogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL REFERENCES incident_records(id) ON DELETE CASCADE,
                work_date TEXT NOT NULL,
                technician_name TEXT NOT NULL,
                technician_id TEXT,
                duration_minutes INTEGER NOT NULL,
                hourly_rate REAL NOT NULL DEFAULT 0.0,
                billable INTEGER NOT NULL DEFAULT 1,
                work_summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # 6. Subtasks
            conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL REFERENCES incident_records(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                assigned_technician TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                is_critical INTEGER NOT NULL DEFAULT 0,
                sequence_order INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            """)

            # 7. Business Rules
            conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_business_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name TEXT NOT NULL UNIQUE,
                description TEXT,
                trigger_event TEXT NOT NULL DEFAULT 'CREATE',
                execution_order INTEGER NOT NULL DEFAULT 10,
                is_active INTEGER NOT NULL DEFAULT 1,
                match_condition TEXT NOT NULL DEFAULT 'ALL',
                criteria TEXT NOT NULL,
                actions TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # 8. Audit Log
            conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL REFERENCES incident_records(id) ON DELETE CASCADE,
                action TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT,
                actor TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Fast Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inc_num ON incident_records(incident_number);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inc_state ON incident_records(state);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inc_priority ON incident_records(priority);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_worklogs_inc ON incident_worklogs(incident_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_subtasks_inc ON incident_subtasks(incident_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_subtasks_seq ON incident_subtasks(incident_id, sequence_order);")


class IncidentEngine:
    """The master ITSM Incident Management facade coordinating all engine subsystems."""

    def __init__(self, db_path: str = ":memory:"):
        self.db = IncidentDatabase(db_path)
        self.priority_matrix = DynamicPriorityMatrix()
        self.sla_engine = PauseableSLAEngine()
        self.seed_defaults()

    def seed_defaults(self) -> None:
        """Seeds taxonomy and business rules idempotently."""
        now_str = to_iso(now_utc())
        with self.db.get_connection() as conn:
            # Seed Taxonomy Trees
            for cat in TAXONOMY_SEEDS:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO incident_categories (code, name, description, is_active, created_at) "
                    "VALUES (?, ?, ?, 1, ?)",
                    (cat["code"], cat["name"], cat["description"], now_str),
                )
                cat_id = cur.lastrowid
                if not cat_id or cat_id == 0:
                    row = conn.execute("SELECT id FROM incident_categories WHERE code = ?", (cat["code"],)).fetchone()
                    cat_id = row["id"]

                for sub in cat.get("subcategories", []):
                    cur_sub = conn.execute(
                        "INSERT OR IGNORE INTO incident_subcategories (category_id, code, name, description, is_active, created_at) "
                        "VALUES (?, ?, ?, ?, 1, ?)",
                        (cat_id, sub["code"], sub["name"], sub["description"], now_str),
                    )
                    sub_id = cur_sub.lastrowid
                    if not sub_id or sub_id == 0:
                        row = conn.execute(
                            "SELECT id FROM incident_subcategories WHERE category_id = ? AND code = ?",
                            (cat_id, sub["code"]),
                        ).fetchone()
                        sub_id = row["id"]

                    for item in sub.get("items", []):
                        conn.execute(
                            "INSERT OR IGNORE INTO incident_items (subcategory_id, code, name, description, is_active, created_at) "
                            "VALUES (?, ?, ?, ?, 1, ?)",
                            (sub_id, item["code"], item["name"], item["description"], now_str),
                        )

            # Seed Business Rules
            for rule in DEFAULT_BUSINESS_RULES:
                conn.execute(
                    "INSERT OR IGNORE INTO incident_business_rules "
                    "(rule_name, description, trigger_event, execution_order, is_active, match_condition, criteria, actions, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rule["rule_name"],
                        rule["description"],
                        rule["trigger_event"],
                        rule["execution_order"],
                        rule["is_active"],
                        rule["match_condition"],
                        json.dumps(rule["criteria"]),
                        json.dumps(rule["actions"]),
                        now_str,
                    ),
                )

    # ------------------------------------------------------------------------
    # TAXONOMY OPERATIONS
    # ------------------------------------------------------------------------

    def get_taxonomy_tree(self) -> List[Dict[str, Any]]:
        """Returns the full 3-tier taxonomy tree (Categories -> Subcategories -> Items)."""
        tree = []
        with self.db.get_connection() as conn:
            cats = conn.execute(
                "SELECT id, code, name, description, is_active FROM incident_categories ORDER BY id"
            ).fetchall()
            for cat in cats:
                cat_dict = dict(cat)
                subs = conn.execute(
                    "SELECT id, category_id, code, name, description, is_active "
                    "FROM incident_subcategories WHERE category_id = ? ORDER BY id",
                    (cat["id"],),
                ).fetchall()
                sub_list = []
                for sub in subs:
                    sub_dict = dict(sub)
                    items = conn.execute(
                        "SELECT id, subcategory_id, code, name, description, is_active "
                        "FROM incident_items WHERE subcategory_id = ? ORDER BY id",
                        (sub["id"],),
                    ).fetchall()
                    sub_dict["items"] = [dict(it) for it in items]
                    sub_list.append(sub_dict)
                cat_dict["subcategories"] = sub_list
                tree.append(cat_dict)
        return tree

    def validate_taxonomy_selection(
        self,
        category_id: Optional[int],
        subcategory_id: Optional[int],
        item_id: Optional[int],
    ) -> bool:
        """Validates that category, subcategory, and item form a valid hierarchical lineage."""
        if not category_id and not subcategory_id and not item_id:
            return True

        with self.db.get_connection() as conn:
            if category_id:
                cat = conn.execute("SELECT id FROM incident_categories WHERE id = ?", (category_id,)).fetchone()
                if not cat:
                    raise TaxonomyValidationError(f"Category ID {category_id} does not exist.")

            if subcategory_id:
                sub = conn.execute(
                    "SELECT id, category_id FROM incident_subcategories WHERE id = ?", (subcategory_id,)
                ).fetchone()
                if not sub:
                    raise TaxonomyValidationError(f"Subcategory ID {subcategory_id} does not exist.")
                if category_id and sub["category_id"] != category_id:
                    raise TaxonomyValidationError(
                        f"Subcategory ID {subcategory_id} does not belong to Category ID {category_id}."
                    )

            if item_id:
                it = conn.execute(
                    "SELECT id, subcategory_id FROM incident_items WHERE id = ?", (item_id,)
                ).fetchone()
                if not it:
                    raise TaxonomyValidationError(f"Item ID {item_id} does not exist.")
                if subcategory_id and it["subcategory_id"] != subcategory_id:
                    raise TaxonomyValidationError(
                        f"Item ID {item_id} does not belong to Subcategory ID {subcategory_id}."
                    )
        return True

    def add_category(self, code: str, name: str, description: str = "") -> int:
        now_str = to_iso(now_utc())
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO incident_categories (code, name, description, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                (code.upper(), name, description, now_str),
            )
            return cur.lastrowid

    def add_subcategory(self, category_id: int, code: str, name: str, description: str = "") -> int:
        now_str = to_iso(now_utc())
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO incident_subcategories (category_id, code, name, description, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                (category_id, code.upper(), name, description, now_str),
            )
            return cur.lastrowid

    def add_item(self, subcategory_id: int, code: str, name: str, description: str = "") -> int:
        now_str = to_iso(now_utc())
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO incident_items (subcategory_id, code, name, description, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                (subcategory_id, code.upper(), name, description, now_str),
            )
            return cur.lastrowid

    # ------------------------------------------------------------------------
    # INCIDENT RECORD MANAGEMENT
    # ------------------------------------------------------------------------

    def _generate_incident_number(self, conn: sqlite3.Connection) -> str:
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
        row = conn.execute(
            "SELECT count(*) as cnt FROM incident_records WHERE incident_number LIKE ?",
            (f"INC-{today_str}-%",),
        ).fetchone()
        seq = (row["cnt"] or 0) + 1
        return f"INC-{today_str}-{seq:04d}"

    def create_incident(
        self,
        title: str,
        description: str,
        impact: Union[int, str] = 3,
        urgency: Union[int, str] = 3,
        category_id: Optional[int] = None,
        subcategory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        caller_name: Optional[str] = None,
        caller_email: Optional[str] = None,
        assigned_to: Optional[str] = None,
        assignment_group: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        initial_state: str = IncidentState.SUBMITTED.value,
        apply_rules: bool = True,
    ) -> Dict[str, Any]:
        """Creates a new incident record with SLA computation and business rules evaluation."""
        self.validate_taxonomy_selection(category_id, subcategory_id, item_id)
        
        norm_impact = DynamicPriorityMatrix.normalize_impact(impact)
        norm_urgency = DynamicPriorityMatrix.normalize_urgency(urgency)
        priority = self.priority_matrix.calculate_priority(norm_impact, norm_urgency)

        now = now_utc()
        now_str = to_iso(now)
        sla_calc = self.sla_engine.calculate_initial_sla(priority, now)

        tags_json = json.dumps(tags or [])
        custom_json = json.dumps(custom_fields or {})

        # Prepare preliminary dict for rules evaluation
        temp_dict: Dict[str, Any] = {
            "title": title,
            "description": description,
            "impact": norm_impact,
            "urgency": norm_urgency,
            "priority": priority,
            "state": initial_state,
            "category_id": category_id,
            "subcategory_id": subcategory_id,
            "item_id": item_id,
            "caller_name": caller_name,
            "caller_email": caller_email,
            "assigned_to": assigned_to,
            "assignment_group": assignment_group,
            "tags": tags or [],
            "custom_fields": custom_fields or {},
        }

        # Populate names for rules
        with self.db.get_connection() as conn:
            if category_id:
                c = conn.execute("SELECT name FROM incident_categories WHERE id = ?", (category_id,)).fetchone()
                if c:
                    temp_dict["category_name"] = c["name"]
            if subcategory_id:
                s = conn.execute("SELECT name FROM incident_subcategories WHERE id = ?", (subcategory_id,)).fetchone()
                if s:
                    temp_dict["subcategory_name"] = s["name"]

        escalation_level = 0
        is_escalated = 0
        side_effects_to_run = []

        if apply_rules:
            rules = self.list_business_rules(trigger_event="CREATE", active_only=True)
            for r in rules:
                if BusinessRulesEngine.evaluate_rule(r, temp_dict):
                    muts, s_effects = BusinessRulesEngine.apply_actions(r.get("actions", "[]"), temp_dict)
                    side_effects_to_run.extend(s_effects)
                    if "assignment_group" in muts:
                        assignment_group = muts["assignment_group"]
                    if "assigned_to" in muts:
                        assigned_to = muts["assigned_to"]
                    if "priority" in muts:
                        priority = muts["priority"]
                        # Recalculate SLA due dates on priority change
                        sla_calc = self.sla_engine.calculate_initial_sla(priority, now)
                    if "is_escalated" in muts:
                        is_escalated = muts["is_escalated"]
                    if "escalation_level" in muts:
                        escalation_level = muts["escalation_level"]
                    if "tags" in muts:
                        tags_json = muts["tags"]

        with self.db.get_connection() as conn:
            inc_number = self._generate_incident_number(conn)
            cur = conn.execute(
                """
                INSERT INTO incident_records (
                    incident_number, title, description, category_id, subcategory_id, item_id,
                    impact, urgency, priority, state, caller_name, caller_email,
                    assigned_to, assignment_group, total_paused_seconds, is_paused,
                    response_sla_target_seconds, resolution_sla_target_seconds,
                    response_sla_due, resolution_sla_due, escalation_level, is_escalated,
                    tags, custom_fields, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inc_number,
                    title,
                    description,
                    category_id,
                    subcategory_id,
                    item_id,
                    norm_impact,
                    norm_urgency,
                    priority,
                    initial_state,
                    caller_name,
                    caller_email,
                    assigned_to,
                    assignment_group,
                    sla_calc["response_sla_target_seconds"],
                    sla_calc["resolution_sla_target_seconds"],
                    sla_calc["response_sla_due"],
                    sla_calc["resolution_sla_due"],
                    escalation_level,
                    is_escalated,
                    tags_json,
                    custom_json,
                    now_str,
                    now_str,
                ),
            )
            incident_id = cur.lastrowid

            # Audit record
            conn.execute(
                "INSERT INTO incident_audit_log (incident_id, action, from_state, to_state, actor, details, created_at) "
                "VALUES (?, 'CREATE', NULL, ?, ?, ?, ?)",
                (
                    incident_id,
                    initial_state,
                    caller_name or "System",
                    json.dumps({"priority": priority, "escalation": is_escalated}),
                    now_str,
                ),
            )

        # Handle side-effect actions (like auto-adding subtasks)
        for s_act in side_effects_to_run:
            if s_act.get("action") == "add_subtask":
                self.add_subtask(
                    incident_id=incident_id,
                    title=s_act.get("title", "Automated Task"),
                    description=s_act.get("description", "Created by business rule"),
                    is_critical=s_act.get("is_critical", False),
                )

        return self.get_incident(incident_id)

    def get_incident(self, incident_id: int) -> Dict[str, Any]:
        """Retrieves incident record by ID with joined category names and SLA metrics."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT r.*,
                       c.name AS category_name,
                       s.name AS subcategory_name,
                       i.name AS item_name
                FROM incident_records r
                LEFT JOIN incident_categories c ON r.category_id = c.id
                LEFT JOIN incident_subcategories s ON r.subcategory_id = s.id
                LEFT JOIN incident_items i ON r.item_id = i.id
                WHERE r.id = ?
                """,
                (incident_id,),
            ).fetchone()
            if not row:
                raise IncidentModuleError(f"Incident with ID {incident_id} not found.")

            data = dict(row)
            # Parse JSON fields
            data["tags"] = json.loads(data.get("tags") or "[]")
            data["custom_fields"] = json.loads(data.get("custom_fields") or "{}")

            # Enrich with calculated SLA metrics
            sla_metrics = self.sla_engine.compute_sla_metrics(data)
            data["sla_metrics"] = sla_metrics

            return data

    def get_incident_by_number(self, incident_number: str) -> Dict[str, Any]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT id FROM incident_records WHERE incident_number = ?", (incident_number,)).fetchone()
            if not row:
                raise IncidentModuleError(f"Incident {incident_number} not found.")
            return self.get_incident(row["id"])

    # ------------------------------------------------------------------------
    # STATE MACHINE TRANSITIONS & GUARDS
    # ------------------------------------------------------------------------

    def transition_state(
        self,
        incident_id: int,
        to_state: Union[str, IncidentState],
        actor: str = "Technician",
        resolution_code: Optional[str] = None,
        root_cause: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        pause_reason: Optional[str] = None,
        cancellation_reason: Optional[str] = None,
        assigned_to: Optional[str] = None,
        assignment_group: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes a state transition with ITSM guard validation and SLA pause/resume handling."""
        inc = self.get_incident(incident_id)
        from_state = inc["state"]
        target_state = to_state.value if isinstance(to_state, IncidentState) else str(to_state)

        # Merge prospective fields for guard validation
        prospective = dict(inc)
        if resolution_code is not None:
            prospective["resolution_code"] = resolution_code
        if root_cause is not None:
            prospective["root_cause"] = root_cause
        if resolution_notes is not None:
            prospective["resolution_notes"] = resolution_notes
        if pause_reason is not None:
            prospective["pause_reason"] = pause_reason
        if cancellation_reason is not None:
            prospective["cancellation_reason"] = cancellation_reason
        if assigned_to is not None:
            prospective["assigned_to"] = assigned_to
        if assignment_group is not None:
            prospective["assignment_group"] = assignment_group

        # Check critical subtasks before resolution
        open_critical_tasks = []
        if target_state == IncidentState.RESOLVED.value:
            open_critical_tasks = self.get_open_critical_subtasks(incident_id)

        # Validate through State Machine and Guards
        IncidentStateMachine.validate_transition(
            from_state=from_state,
            to_state=target_state,
            incident_data=prospective,
            open_critical_subtasks=open_critical_tasks,
        )

        now = now_utc()
        now_str = to_iso(now)

        # Calculate SLA pause / resume adjustments
        sla_adjustments = self.sla_engine.process_state_pause_resume(
            from_state=from_state,
            to_state=target_state,
            incident_dict=inc,
            event_time=now,
        )

        # Build SQL updates
        updates: Dict[str, Any] = {
            "state": target_state,
            "updated_at": now_str,
        }
        updates.update(sla_adjustments)

        if resolution_code:
            updates["resolution_code"] = resolution_code
        if root_cause:
            updates["root_cause"] = root_cause
        if resolution_notes:
            updates["resolution_notes"] = resolution_notes
        if pause_reason:
            updates["pause_reason"] = pause_reason
        if cancellation_reason:
            updates["cancellation_reason"] = cancellation_reason
        if assigned_to:
            updates["assigned_to"] = assigned_to
        if assignment_group:
            updates["assignment_group"] = assignment_group

        # Timestamp tracking
        if target_state in (IncidentState.ASSIGNED.value, IncidentState.IN_PROGRESS.value):
            if not inc.get("first_responded_at"):
                updates["first_responded_at"] = now_str

        if target_state == IncidentState.RESOLVED.value:
            updates["resolved_at"] = now_str
        elif from_state == IncidentState.RESOLVED.value and target_state == IncidentState.IN_PROGRESS.value:
            # Reopening incident: clear resolved_at
            updates["resolved_at"] = None

        if target_state == IncidentState.CLOSED.value:
            updates["closed_at"] = now_str

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [incident_id]

        with self.db.get_connection() as conn:
            conn.execute(f"UPDATE incident_records SET {set_clause} WHERE id = ?", values)

            # Audit log
            audit_details = {
                "actor": actor,
                "notes": resolution_notes or pause_reason or cancellation_reason or "",
                "sla_paused": updates.get("is_paused", inc.get("is_paused")),
            }
            conn.execute(
                "INSERT INTO incident_audit_log (incident_id, action, from_state, to_state, actor, details, created_at) "
                "VALUES (?, 'STATE_CHANGE', ?, ?, ?, ?, ?)",
                (incident_id, from_state, target_state, actor, json.dumps(audit_details), now_str),
            )

        return self.get_incident(incident_id)

    # ------------------------------------------------------------------------
    # WORKLOGS & LABOR COST TRACKING
    # ------------------------------------------------------------------------

    def add_worklog(
        self,
        incident_id: int,
        technician_name: str,
        duration_minutes: int,
        hourly_rate: float,
        billable: bool = True,
        work_summary: str = "",
        technician_id: Optional[str] = None,
        work_date: Optional[str] = None,
    ) -> int:
        """Adds a technician labor worklog to the incident."""
        if duration_minutes <= 0:
            raise IncidentModuleError("Worklog duration_minutes must be greater than 0.")
        if hourly_rate < 0:
            raise IncidentModuleError("Worklog hourly_rate cannot be negative.")

        now_str = to_iso(now_utc())
        date_str = work_date or now_str

        with self.db.get_connection() as conn:
            # Verify incident exists
            row = conn.execute("SELECT id FROM incident_records WHERE id = ?", (incident_id,)).fetchone()
            if not row:
                raise IncidentModuleError(f"Incident ID {incident_id} not found.")

            cur = conn.execute(
                """
                INSERT INTO incident_worklogs (
                    incident_id, work_date, technician_name, technician_id,
                    duration_minutes, hourly_rate, billable, work_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    date_str,
                    technician_name,
                    technician_id,
                    duration_minutes,
                    float(hourly_rate),
                    1 if billable else 0,
                    work_summary,
                    now_str,
                ),
            )
            worklog_id = cur.lastrowid

            # Mark first response if technician adds worklog and first_responded_at is null
            conn.execute(
                "UPDATE incident_records SET first_responded_at = COALESCE(first_responded_at, ?) WHERE id = ?",
                (now_str, incident_id),
            )

            # Audit
            conn.execute(
                "INSERT INTO incident_audit_log (incident_id, action, from_state, to_state, actor, details, created_at) "
                "VALUES (?, 'WORKLOG_ADDED', NULL, NULL, ?, ?, ?)",
                (
                    incident_id,
                    technician_name,
                    json.dumps({"duration_minutes": duration_minutes, "hourly_rate": hourly_rate, "billable": billable}),
                    now_str,
                ),
            )
            return worklog_id

    def get_worklogs(self, incident_id: int) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM incident_worklogs WHERE incident_id = ? ORDER BY id ASC", (incident_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def calculate_labor_cost_summary(self, incident_id: int) -> Dict[str, Any]:
        """Calculates total labor cost, billable vs non-billable hours, and technician breakdown."""
        worklogs = self.get_worklogs(incident_id)

        total_minutes = 0
        billable_minutes = 0
        non_billable_minutes = 0
        total_cost = 0.0
        billable_cost = 0.0
        technicians: Dict[str, Dict[str, Any]] = {}

        for w in worklogs:
            mins = int(w["duration_minutes"])
            rate = float(w["hourly_rate"])
            is_billable = bool(w["billable"])
            cost = (mins / 60.0) * rate

            total_minutes += mins
            total_cost += cost

            if is_billable:
                billable_minutes += mins
                billable_cost += cost
            else:
                non_billable_minutes += mins

            tech = w["technician_name"]
            if tech not in technicians:
                technicians[tech] = {
                    "total_minutes": 0,
                    "total_hours": 0.0,
                    "billable_hours": 0.0,
                    "cost": 0.0,
                    "entries": 0,
                }
            technicians[tech]["total_minutes"] += mins
            technicians[tech]["total_hours"] = round(technicians[tech]["total_minutes"] / 60.0, 2)
            if is_billable:
                technicians[tech]["billable_hours"] = round(
                    technicians[tech]["billable_hours"] + (mins / 60.0), 2
                )
            technicians[tech]["cost"] = round(technicians[tech]["cost"] + cost, 2)
            technicians[tech]["entries"] += 1

        total_hours = round(total_minutes / 60.0, 2)
        billable_hours = round(billable_minutes / 60.0, 2)
        non_billable_hours = round(non_billable_minutes / 60.0, 2)

        return {
            "incident_id": incident_id,
            "worklog_count": len(worklogs),
            "total_minutes": total_minutes,
            "total_hours": total_hours,
            "billable_minutes": billable_minutes,
            "billable_hours": billable_hours,
            "non_billable_hours": non_billable_hours,
            "total_labor_cost": round(total_cost, 2),
            "billable_labor_cost": round(billable_cost, 2),
            "by_technician": technicians,
        }

    # ------------------------------------------------------------------------
    # SUBTASKS MANAGEMENT
    # ------------------------------------------------------------------------

    def add_subtask(
        self,
        incident_id: int,
        title: str,
        description: str = "",
        assigned_technician: Optional[str] = None,
        is_critical: bool = False,
        sequence_order: Optional[int] = None,
    ) -> int:
        """Adds a sequenced subtask to an incident."""
        now_str = to_iso(now_utc())
        with self.db.get_connection() as conn:
            # Check incident existence
            row = conn.execute("SELECT id FROM incident_records WHERE id = ?", (incident_id,)).fetchone()
            if not row:
                raise IncidentModuleError(f"Incident ID {incident_id} does not exist.")

            if sequence_order is None:
                max_seq = conn.execute(
                    "SELECT MAX(sequence_order) as m FROM incident_subtasks WHERE incident_id = ?",
                    (incident_id,),
                ).fetchone()["m"]
                sequence_order = (max_seq or 0) + 1

            cur = conn.execute(
                """
                INSERT INTO incident_subtasks (
                    incident_id, title, description, assigned_technician,
                    status, is_critical, sequence_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'Pending', ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    title,
                    description,
                    assigned_technician,
                    1 if is_critical else 0,
                    sequence_order,
                    now_str,
                    now_str,
                ),
            )
            subtask_id = cur.lastrowid

            conn.execute(
                "INSERT INTO incident_audit_log (incident_id, action, from_state, to_state, actor, details, created_at) "
                "VALUES (?, 'SUBTASK_ADDED', NULL, NULL, ?, ?, ?)",
                (
                    incident_id,
                    assigned_technician or "System",
                    json.dumps({"subtask_id": subtask_id, "title": title, "is_critical": is_critical}),
                    now_str,
                ),
            )
            return subtask_id

    def update_subtask_status(
        self, subtask_id: int, status: Union[str, SubtaskStatus], actor: str = "Technician"
    ) -> Dict[str, Any]:
        """Updates status of a subtask and marks completed_at if completed."""
        norm_status = status.value if isinstance(status, SubtaskStatus) else str(status)
        valid_statuses = {s.value for s in SubtaskStatus}
        if norm_status not in valid_statuses:
            raise SubtaskError(f"Invalid subtask status '{status}'. Must be one of {valid_statuses}")

        now = now_utc()
        now_str = to_iso(now)
        completed_at = now_str if norm_status == SubtaskStatus.COMPLETED.value else None

        with self.db.get_connection() as conn:
            sub = conn.execute("SELECT * FROM incident_subtasks WHERE id = ?", (subtask_id,)).fetchone()
            if not sub:
                raise SubtaskError(f"Subtask with ID {subtask_id} not found.")

            conn.execute(
                """
                UPDATE incident_subtasks
                SET status = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (norm_status, completed_at, now_str, subtask_id),
            )

            conn.execute(
                "INSERT INTO incident_audit_log (incident_id, action, from_state, to_state, actor, details, created_at) "
                "VALUES (?, 'SUBTASK_STATUS_CHANGED', ?, ?, ?, ?, ?)",
                (
                    sub["incident_id"],
                    sub["status"],
                    norm_status,
                    actor,
                    json.dumps({"subtask_id": subtask_id, "title": sub["title"]}),
                    now_str,
                ),
            )

            row = conn.execute("SELECT * FROM incident_subtasks WHERE id = ?", (subtask_id,)).fetchone()
            return dict(row)

    def reorder_subtasks(self, incident_id: int, subtask_order_ids: Sequence[int]) -> List[Dict[str, Any]]:
        """Reorders subtasks according to provided ID sequence."""
        now_str = to_iso(now_utc())
        with self.db.get_connection() as conn:
            for idx, s_id in enumerate(subtask_order_ids, start=1):
                conn.execute(
                    "UPDATE incident_subtasks SET sequence_order = ?, updated_at = ? WHERE id = ? AND incident_id = ?",
                    (idx, now_str, s_id, incident_id),
                )
        return self.get_subtasks(incident_id)

    def get_subtasks(self, incident_id: int) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM incident_subtasks WHERE incident_id = ? ORDER BY sequence_order ASC, id ASC",
                (incident_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_open_critical_subtasks(self, incident_id: int) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM incident_subtasks
                WHERE incident_id = ?
                  AND is_critical = 1
                  AND status NOT IN ('Completed', 'Cancelled')
                ORDER BY sequence_order ASC
                """,
                (incident_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------------
    # BUSINESS RULES CRUD & EXECUTION
    # ------------------------------------------------------------------------

    def add_business_rule(
        self,
        rule_name: str,
        criteria: List[Dict[str, Any]],
        actions: List[Dict[str, Any]],
        description: str = "",
        trigger_event: str = "CREATE",
        execution_order: int = 10,
        match_condition: str = "ALL",
        is_active: bool = True,
    ) -> int:
        now_str = to_iso(now_utc())
        with self.db.get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO incident_business_rules (
                    rule_name, description, trigger_event, execution_order,
                    is_active, match_condition, criteria, actions, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule_name,
                    description,
                    trigger_event,
                    execution_order,
                    1 if is_active else 0,
                    match_condition,
                    json.dumps(criteria),
                    json.dumps(actions),
                    now_str,
                ),
            )
            return cur.lastrowid

    def list_business_rules(
        self, trigger_event: Optional[str] = None, active_only: bool = True
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM incident_business_rules WHERE 1=1"
        params: List[Any] = []
        if active_only:
            query += " AND is_active = 1"
        if trigger_event:
            query += " AND (trigger_event = ? OR trigger_event = 'ANY')"
            params.append(trigger_event)
        query += " ORDER BY execution_order ASC, id ASC"

        with self.db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["criteria"] = json.loads(item["criteria"])
                item["actions"] = json.loads(item["actions"])
                results.append(item)
            return results

    # ------------------------------------------------------------------------
    # AUDIT LOG
    # ------------------------------------------------------------------------

    def get_audit_trail(self, incident_id: int) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM incident_audit_log WHERE incident_id = ? ORDER BY id ASC", (incident_id,)
            ).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                if d.get("details"):
                    try:
                        d["details"] = json.loads(d["details"])
                    except Exception:
                        pass
                res.append(d)
            return res


# ============================================================================
# 7. COMPREHENSIVE UNIT TEST SUITE
# ============================================================================

class TestIncidentModule(unittest.TestCase):
    """Rigorous unit test suite validating all 8 incident management pillars."""

    def setUp(self):
        # In-memory database for isolated, lightning-fast testing
        self.engine = IncidentEngine(":memory:")

    # --- 1. Three-Tier Taxonomy Tests ---
    def test_01_taxonomy_pre_seeded_tree(self):
        tree = self.engine.get_taxonomy_tree()
        cat_codes = {c["code"] for c in tree}
        self.assertIn("HARDWARE", cat_codes)
        self.assertIn("SOFTWARE", cat_codes)
        self.assertIn("NETWORK", cat_codes)
        self.assertIn("DATABASE", cat_codes)
        self.assertIn("ERP", cat_codes)
        self.assertIn("IT_SERVICES", cat_codes)

        # Check subcategories and items under Database
        db_cat = next(c for c in tree if c["code"] == "DATABASE")
        sub_codes = {s["code"] for s in db_cat["subcategories"]}
        self.assertIn("POSTGRESQL", sub_codes)
        self.assertIn("ORACLE_DB", sub_codes)

        pg_sub = next(s for s in db_cat["subcategories"] if s["code"] == "POSTGRESQL")
        item_codes = {it["code"] for it in pg_sub["items"]}
        self.assertIn("PG_CONN_EXHAUSTED", item_codes)
        self.assertIn("PG_DEADLOCK", item_codes)

    def test_02_taxonomy_validation_hierarchy(self):
        # Valid hierarchy
        tree = self.engine.get_taxonomy_tree()
        hw_cat = next(c for c in tree if c["code"] == "HARDWARE")
        sub = hw_cat["subcategories"][0]
        it = sub["items"][0]

        # Valid combination
        self.assertTrue(self.engine.validate_taxonomy_selection(hw_cat["id"], sub["id"], it["id"]))

        # Mismatched combination: Item from HW with Software subcategory
        sw_cat = next(c for c in tree if c["code"] == "SOFTWARE")
        sw_sub = sw_cat["subcategories"][0]
        with self.assertRaises(TaxonomyValidationError):
            self.engine.validate_taxonomy_selection(sw_cat["id"], sw_sub["id"], it["id"])

    # --- 2. Dynamic Priority Matrix Tests ---
    def test_03_priority_matrix_itil_defaults(self):
        matrix = self.engine.priority_matrix
        # Enterprise x Critical -> P1
        self.assertEqual(matrix.calculate_priority(1, 1), "P1")
        # Enterprise x High -> P1
        self.assertEqual(matrix.calculate_priority(1, 2), "P1")
        # Enterprise x Medium -> P2
        self.assertEqual(matrix.calculate_priority(1, 3), "P2")
        # Enterprise x Low -> P3
        self.assertEqual(matrix.calculate_priority(1, 4), "P3")

        # Department x Critical -> P2
        self.assertEqual(matrix.calculate_priority(2, 1), "P2")
        # Department x Low -> P4
        self.assertEqual(matrix.calculate_priority(2, 4), "P4")

        # Single User x Critical -> P3
        self.assertEqual(matrix.calculate_priority(3, 1), "P3")
        # Single User x Low -> P4
        self.assertEqual(matrix.calculate_priority(3, 4), "P4")

    def test_04_priority_matrix_dynamic_overrides(self):
        matrix = DynamicPriorityMatrix()
        # Override Single User x Critical to P1
        matrix.set_rule(impact=3, urgency=1, priority="P1")
        self.assertEqual(matrix.calculate_priority(3, 1), "P1")

        # Text input normalization
        self.assertEqual(matrix.calculate_priority("Single User", "1 - Critical"), "P1")
        self.assertEqual(matrix.calculate_priority("Enterprise", "Low"), "P3")

    # --- 3. Incident Lifecycle State Machine & Guards ---
    def test_05_lifecycle_happy_path(self):
        # Create incident
        inc = self.engine.create_incident(
            title="Printer Paper Jam",
            description="Lobby printer paper jam",
            impact=3,
            urgency=4,
            caller_name="Alice Smith",
            apply_rules=False,
        )
        self.assertEqual(inc["state"], IncidentState.SUBMITTED.value)
        self.assertEqual(inc["priority"], "P4")

        # Transition to Assigned
        inc = self.engine.transition_state(
            incident_id=inc["id"],
            to_state=IncidentState.ASSIGNED.value,
            assigned_to="Bob Technician",
        )
        self.assertEqual(inc["state"], IncidentState.ASSIGNED.value)
        self.assertEqual(inc["assigned_to"], "Bob Technician")

        # Transition to In_Progress
        inc = self.engine.transition_state(
            incident_id=inc["id"],
            to_state=IncidentState.IN_PROGRESS.value,
        )
        self.assertEqual(inc["state"], IncidentState.IN_PROGRESS.value)

        # Transition to Resolved (with guards satisfied)
        inc = self.engine.transition_state(
            incident_id=inc["id"],
            to_state=IncidentState.RESOLVED.value,
            resolution_code="SOLVED_HARDWARE",
            root_cause="Paper roller misaligned",
            resolution_notes="Removed jammed tray and realigned rollers.",
        )
        self.assertEqual(inc["state"], IncidentState.RESOLVED.value)
        self.assertIsNotNone(inc["resolved_at"])

        # Transition to Closed
        inc = self.engine.transition_state(
            incident_id=inc["id"],
            to_state=IncidentState.CLOSED.value,
        )
        self.assertEqual(inc["state"], IncidentState.CLOSED.value)
        self.assertIsNotNone(inc["closed_at"])

    def test_06_lifecycle_illegal_transition_rejection(self):
        inc = self.engine.create_incident(
            title="Outlook crash",
            description="Outlook crashes on startup",
            initial_state=IncidentState.DRAFT.value,
            apply_rules=False,
        )
        # Draft -> Resolved directly is illegal
        with self.assertRaises(InvalidStateTransitionError):
            self.engine.transition_state(inc["id"], IncidentState.RESOLVED.value)

    def test_07_transition_guard_resolution_fields(self):
        inc = self.engine.create_incident(
            title="VPN drops",
            description="Drops every 10 mins",
            initial_state=IncidentState.IN_PROGRESS.value,
            apply_rules=False,
        )
        # Attempt to resolve without resolution notes
        with self.assertRaises(TransitionGuardError) as ctx:
            self.engine.transition_state(
                inc["id"],
                IncidentState.RESOLVED.value,
                resolution_code="SOLVED",
                root_cause="Bad route",
                resolution_notes="",  # Empty notes
            )
        self.assertIn("Missing required resolution fields", str(ctx.exception))

    def test_08_transition_guard_pending_pause_reason(self):
        inc = self.engine.create_incident(
            title="Need info from user",
            description="Waiting for screenshots",
            initial_state=IncidentState.IN_PROGRESS.value,
            apply_rules=False,
        )
        # Attempt to move to Pending_Customer without pause_reason
        with self.assertRaises(TransitionGuardError):
            self.engine.transition_state(
                inc["id"],
                IncidentState.PENDING_CUSTOMER.value,
                pause_reason="",
            )

        # Successful when pause_reason is given
        res = self.engine.transition_state(
            inc["id"],
            IncidentState.PENDING_CUSTOMER.value,
            pause_reason="Awaiting screenshot of error dialog from caller.",
        )
        self.assertEqual(res["state"], IncidentState.PENDING_CUSTOMER.value)
        self.assertEqual(res["is_paused"], 1)

    def test_09_reopen_incident(self):
        inc = self.engine.create_incident(
            title="Monitor flicker",
            description="Flickering HDMI",
            initial_state=IncidentState.IN_PROGRESS.value,
            apply_rules=False,
        )
        inc = self.engine.transition_state(
            inc["id"],
            IncidentState.RESOLVED.value,
            resolution_code="FIXED",
            root_cause="Loose cable",
            resolution_notes="Reseated HDMI cable.",
        )
        self.assertEqual(inc["state"], IncidentState.RESOLVED.value)

        # Reopen (Resolved -> In_Progress)
        reopened = self.engine.transition_state(
            inc["id"],
            IncidentState.IN_PROGRESS.value,
            actor="Caller Reopened",
        )
        self.assertEqual(reopened["state"], IncidentState.IN_PROGRESS.value)
        self.assertIsNone(reopened["resolved_at"])

    # --- 4. Subtasks & Resolution Blocking Guard ---
    def test_10_critical_subtask_blocks_resolution(self):
        inc = self.engine.create_incident(
            title="Database Upgrade Incident",
            description="Cluster maintenance outage",
            initial_state=IncidentState.IN_PROGRESS.value,
            apply_rules=False,
        )
        # Add non-critical subtask
        self.engine.add_subtask(inc["id"], title="Notify stakeholders", is_critical=False)
        # Add critical subtask
        crit_id = self.engine.add_subtask(
            inc["id"], title="Verify replica synchronization", is_critical=True
        )

        # Attempt to resolve incident while critical subtask is Pending
        with self.assertRaises(TransitionGuardError) as ctx:
            self.engine.transition_state(
                inc["id"],
                IncidentState.RESOLVED.value,
                resolution_code="MAINT_COMPLETE",
                root_cause="Scheduled migration",
                resolution_notes="DB upgraded successfully.",
            )
        self.assertIn("critical subtask(s) are incomplete", str(ctx.exception))

        # Complete the critical subtask
        self.engine.update_subtask_status(crit_id, SubtaskStatus.COMPLETED)

        # Now resolution succeeds
        resolved = self.engine.transition_state(
            inc["id"],
            IncidentState.RESOLVED.value,
            resolution_code="MAINT_COMPLETE",
            root_cause="Scheduled migration",
            resolution_notes="DB upgraded and verified successfully.",
        )
        self.assertEqual(resolved["state"], IncidentState.RESOLVED.value)

    def test_11_subtask_sequencing_and_reordering(self):
        inc = self.engine.create_incident(
            title="Multi-step repair",
            description="Replace logic board and run diagnostics",
            apply_rules=False,
        )
        s1 = self.engine.add_subtask(inc["id"], title="Step 1: Backup disk")
        s2 = self.engine.add_subtask(inc["id"], title="Step 2: Replace board")
        s3 = self.engine.add_subtask(inc["id"], title="Step 3: Run hardware tests")

        subtasks = self.engine.get_subtasks(inc["id"])
        self.assertEqual([s["id"] for s in subtasks], [s1, s2, s3])

        # Reverse order
        reordered = self.engine.reorder_subtasks(inc["id"], [s3, s2, s1])
        self.assertEqual([s["id"] for s in reordered], [s3, s2, s1])
        self.assertEqual(reordered[0]["sequence_order"], 1)
        self.assertEqual(reordered[2]["sequence_order"], 3)

    # --- 5. Pauseable SLA Engine Tests ---
    def test_12_sla_pause_and_resume_extension(self):
        # Create P1 incident (2-hour resolution SLA, 24x7)
        inc = self.engine.create_incident(
            title="Core Router Down",
            description="Campus Core unreachable",
            impact=1,
            urgency=1,
            initial_state=IncidentState.IN_PROGRESS.value,
            apply_rules=False,
        )
        self.assertEqual(inc["priority"], "P1")
        orig_res_due = from_iso(inc["resolution_sla_due"])
        self.assertIsNotNone(orig_res_due)

        # Pause SLA: Move to Pending_Vendor
        pause_start = now_utc()
        self.engine.transition_state(
            inc["id"],
            IncidentState.PENDING_VENDOR.value,
            pause_reason="Cisco TAC hardware dispatch in progress.",
        )

        paused_inc = self.engine.get_incident(inc["id"])
        self.assertEqual(paused_inc["is_paused"], 1)
        self.assertIsNotNone(paused_inc["paused_at"])

        # Simulate 1 hour (3600 seconds) passing during vendor pause
        past_pause_start = now_utc() - datetime.timedelta(seconds=3600)
        with self.engine.db.get_connection() as conn:
            conn.execute(
                "UPDATE incident_records SET paused_at = ? WHERE id = ?",
                (to_iso(past_pause_start), inc["id"]),
            )

        resumed_inc = self.engine.transition_state(
            inc["id"],
            IncidentState.IN_PROGRESS.value,
            actor="Cisco Engineer on-site",
        )
        self.assertEqual(resumed_inc["state"], IncidentState.IN_PROGRESS.value)
        self.assertEqual(resumed_inc["is_paused"], 0)
        self.assertGreaterEqual(resumed_inc["total_paused_seconds"], 3600)
        self.assertLessEqual(resumed_inc["total_paused_seconds"], 3605)

        new_res_due = from_iso(resumed_inc["resolution_sla_due"])
        diff_seconds = int((new_res_due - orig_res_due).total_seconds())
        self.assertGreaterEqual(diff_seconds, 3600)
        self.assertLessEqual(diff_seconds, 3605)

    def test_13_sla_metrics_breach_detection(self):
        inc = self.engine.create_incident(
            title="Minor issue",
            description="Low urgency",
            impact=3,
            urgency=4,
            apply_rules=False,
        )
        # Simulate time in future beyond resolution SLA
        future_time = now_utc() + datetime.timedelta(days=10)
        metrics = self.engine.sla_engine.compute_sla_metrics(inc, current_time=future_time)
        self.assertTrue(metrics["is_response_breached"])
        self.assertTrue(metrics["is_resolution_breached"])
        self.assertEqual(metrics["resolution_status"], SLAStatus.BREACHED.value)

    # --- 6. Technician Worklogs & Labor Cost Tests ---
    def test_14_worklog_cost_and_hours_calculation(self):
        inc = self.engine.create_incident(
            title="Server SAN rebuild",
            description="Rebuild SAN storage lun",
            apply_rules=False,
        )
        # Technician 1: Billable, 90 mins @ $120/hr = $180.00
        self.engine.add_worklog(
            incident_id=inc["id"],
            technician_name="Carol Senior DBA",
            duration_minutes=90,
            hourly_rate=120.0,
            billable=True,
            work_summary="Storage lun reconstruction and parity verification.",
        )

        # Technician 1: Billable, 30 mins @ $120/hr = $60.00
        self.engine.add_worklog(
            incident_id=inc["id"],
            technician_name="Carol Senior DBA",
            duration_minutes=30,
            hourly_rate=120.0,
            billable=True,
            work_summary="Database cluster online validation.",
        )

        # Technician 2: Non-billable internal training, 60 mins @ $80/hr = $80.00
        self.engine.add_worklog(
            incident_id=inc["id"],
            technician_name="Dave Junior Engineer",
            duration_minutes=60,
            hourly_rate=80.0,
            billable=False,
            work_summary="Shadowing storage rebuild operation.",
        )

        cost_summary = self.engine.calculate_labor_cost_summary(inc["id"])
        self.assertEqual(cost_summary["worklog_count"], 3)
        self.assertEqual(cost_summary["total_minutes"], 180)  # 3.0 hours
        self.assertEqual(cost_summary["total_hours"], 3.0)
        self.assertEqual(cost_summary["billable_minutes"], 120)  # 2.0 hours
        self.assertEqual(cost_summary["billable_hours"], 2.0)
        self.assertEqual(cost_summary["non_billable_hours"], 1.0)
        self.assertEqual(cost_summary["total_labor_cost"], 320.0)    # 240 + 80
        self.assertEqual(cost_summary["billable_labor_cost"], 240.0) # 180 + 60

        # Technician breakdown
        techs = cost_summary["by_technician"]
        self.assertEqual(techs["Carol Senior DBA"]["total_hours"], 2.0)
        self.assertEqual(techs["Carol Senior DBA"]["cost"], 240.0)
        self.assertEqual(techs["Dave Junior Engineer"]["total_hours"], 1.0)
        self.assertEqual(techs["Dave Junior Engineer"]["cost"], 80.0)

    # --- 7. Business Rules Engine Tests ---
    def test_15_business_rules_auto_assignment_and_escalation(self):
        # Fetch category ID for Database
        tree = self.engine.get_taxonomy_tree()
        db_cat = next(c for c in tree if c["code"] == "DATABASE")

        # Create Database incident with Urgency=1 (Critical)
        inc = self.engine.create_incident(
            title="Postgres Production Deadlock Cascade",
            description="All API pods blocked on row lock",
            category_id=db_cat["id"],
            impact=2,
            urgency=1, # Critical
            apply_rules=True,
        )

        # Verified pre-seeded rule RULE_DB_CRITICAL_DBA_ESCALATION was evaluated and applied:
        self.assertEqual(inc["assignment_group"], "DBA-Team")
        self.assertEqual(inc["priority"], "P1")
        self.assertEqual(inc["is_escalated"], 1)
        self.assertEqual(inc["escalation_level"], 1)
        self.assertIn("DBA_HIGH_PRIORITY", inc["tags"])

    def test_16_custom_business_rule_addition_and_execution(self):
        # Add custom rule: If title contains "Cyberattack" -> Escalate to SecOps
        self.engine.add_business_rule(
            rule_name="RULE_SECURITY_INCIDENT_DISPATCH",
            criteria=[{"field": "title", "operator": "contains", "value": "Ransomware"}],
            actions=[
                {"action": "set_field", "field": "assignment_group", "value": "SecOps-Tier3"},
                {"action": "set_field", "field": "priority", "value": "P1"},
                {"action": "trigger_escalation", "level": 3, "reason": "Immediate security threat"},
                {"action": "add_tag", "tag": "INCIDENT_CYBER_CRITICAL"},
            ],
            trigger_event="CREATE",
            execution_order=1,
        )

        inc = self.engine.create_incident(
            title="Ransomware detected on NAS share",
            description="Encrypted files with .locked extension found",
            impact=2,
            urgency=2,
            apply_rules=True,
        )
        self.assertEqual(inc["assignment_group"], "SecOps-Tier3")
        self.assertEqual(inc["priority"], "P1")
        self.assertEqual(inc["escalation_level"], 3)
        self.assertIn("INCIDENT_CYBER_CRITICAL", inc["tags"])

    # --- 8. SQLite Storage & Audit Integrity ---
    def test_17_sqlite_wal_mode_and_audit_trail(self):
        with self.engine.db.get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            # In memory this is 'memory', on disk file it will be 'wal'
            self.assertIn(mode.lower(), ("wal", "memory"))

            fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            self.assertEqual(fk, 1)

        # Verify audit trail
        inc = self.engine.create_incident(
            title="Audit check",
            description="Testing audit entries",
            apply_rules=False,
        )
        self.engine.transition_state(
            inc["id"],
            IncidentState.ASSIGNED.value,
            assigned_to="Engineer Jane",
            actor="Dispatcher",
        )
        trail = self.engine.get_audit_trail(inc["id"])
        self.assertTrue(len(trail) >= 2)
        actions = [e["action"] for e in trail]
        self.assertIn("CREATE", actions)
        self.assertIn("STATE_CHANGE", actions)

    def test_18_disk_sqlite_wal_mode(self):
        import tempfile
        fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            disk_engine = IncidentEngine(temp_path)
            with disk_engine.db.get_connection() as conn:
                journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
                self.assertEqual(journal_mode.lower(), "wal")
                fk_mode = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
                self.assertEqual(fk_mode, 1)

            disk_inc = disk_engine.create_incident(
                title="Disk incident test",
                description="Verifying WAL disk write",
                impact=2,
                urgency=2,
                apply_rules=False,
            )
            self.assertTrue(disk_inc["id"] > 0)
            self.assertTrue(disk_inc["incident_number"].startswith("INC-"))
            disk_engine.db.close()
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            for ext in ("-wal", "-shm"):
                p = temp_path + ext
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass


if __name__ == "__main__":
    print("=" * 80)
    print(" RUNNING OPENNOW INCIDENT MANAGEMENT COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    unittest.main(verbosity=2)
