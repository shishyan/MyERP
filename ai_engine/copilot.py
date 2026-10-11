"""
OpenNow AI Co-Pilot & Automated Reasoning Engine
=================================================
The intelligence and automation layer for OpenNow (AI-native enterprise ITSM).

Key Capabilities:
1. IncidentTriageEngine: Predicts Priority (P1-P4), Category, Assignment Team, Urgency, Sentiment, and CIs.
2. CMDBBlastRadiusEngine: Graph traversal for Upstream Dependencies, Downstream Blast Radius, and System Risk Score (0-100).
3. RunbookSynthesizer: Synthesizes tailored diagnostic CLI commands, remediation runbooks, and verification steps.
4. StakeholderCommunicationsEngine: Formats executive and technical incident broadcasts across incident lifecycles.
5. RuleAutomationEngine: Evaluates SLA thresholds, automated escalations, and incident alert triggers.
"""

from __future__ import annotations

import re
import math
import time
from typing import Dict, List, Optional, Any, Set, Tuple
from pydantic import BaseModel, Field
from collections import deque


# ============================================================================
# PYDANTIC DATA MODELS & SCHEMAS
# ============================================================================

class TriageRequest(BaseModel):
    title: str = Field(..., description="Ticket summary or incident title")
    description: str = Field("", description="Detailed incident description")
    task_id: Optional[str] = Field(None, description="Optional task or ticket identifier")
    reporter: Optional[str] = Field(None, description="User or system reporting the issue")
    environment: Optional[str] = Field("production", description="Affected environment")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class TriageResponse(BaseModel):
    task_id: Optional[str]
    title: str
    recommended_priority: str  # "P1-Critical", "P2-High", "P3-Moderate", "P4-Low"
    priority_code: str         # "P1", "P2", "P3", "P4"
    category: str              # Infrastructure, Security, Database, Network, Application, Payment, Access
    recommended_assignment_team: str  # DevOps/SRE, SecOps, Database Team, Platform Eng, Tier 1 Support, Payment Ops
    urgency_score: float       # 0.0 to 1.0
    sentiment_score: float     # 0.0 (Extremely negative/frustrated) to 1.0 (Calm/Positive)
    sentiment_label: str       # Critical Distress, Frustrated, Neutral, Calm
    identified_cis: List[Dict[str, Any]]  # CIs identified in text
    impact_scope: str          # Enterprise-wide, Multi-service, Single-service, Localized
    sla_response_target: str   # e.g. "15 minutes"
    sla_resolution_target: str # e.g. "1 hour"
    escalation_triggered: bool
    escalation_action: Optional[str]
    tags: List[str]
    reasoning_summary: List[str]


class BlastRadiusRequest(BaseModel):
    ci_id: str = Field(..., description="Target Configuration Item ID (e.g. ci-db-postgres-primary)")
    max_depth: Optional[int] = Field(5, description="Maximum graph traversal depth")


class CIRef(BaseModel):
    ci_id: str
    name: str
    type: str
    tier: str
    environment: str
    owner_team: str
    cascade_depth: int
    relationship_type: str
    status: str = "operational"


class BlastRadiusResponse(BaseModel):
    target_ci: Dict[str, Any]
    upstream_dependencies: List[CIRef]
    downstream_blast_radius: List[CIRef]
    cascade_depth: int
    direct_dependents_count: int
    total_impacted_services: int
    impacted_tier_1_count: int
    system_risk_score: int     # 0 to 100
    risk_level: str            # CRITICAL, HIGH, MEDIUM, LOW
    business_impact_summary: str
    critical_business_operations: List[str]
    recommended_containment: List[str]


class RunbookRequest(BaseModel):
    task_id: Optional[str] = Field(None, description="Incident ticket ID")
    title: Optional[str] = Field(None, description="Incident title if task_id not provided")
    description: Optional[str] = Field(None, description="Incident description")
    category: Optional[str] = Field(None, description="Category override")
    ci_id: Optional[str] = Field(None, description="Target CI ID")


class RunbookStep(BaseModel):
    step_number: int
    phase: str                 # "Diagnostic", "Containment", "Remediation", "Verification", "Rollback"
    title: str
    description: str
    command: Optional[str] = None
    expected_output: Optional[str] = None
    safety_warning: Optional[str] = None


class RunbookResponse(BaseModel):
    task_id: Optional[str]
    runbook_id: str
    runbook_title: str
    category: str
    target_ci: Optional[str]
    estimated_duration: str
    prerequisites: List[str]
    diagnostic_commands: List[str]
    steps: List[RunbookStep]
    verification_steps: List[str]
    rollback_plan: List[str]
    safety_notes: List[str]


class CommunicationDraftRequest(BaseModel):
    task_id: Optional[str] = Field(None, description="Incident ID")
    title: Optional[str] = Field(None, description="Incident title")
    audience: str = Field("stakeholder", description="'stakeholder' (executive/customer) or 'technical' (engineering)")
    phase: str = Field("investigating", description="'investigating', 'identified', 'mitigated', 'resolved'")
    ci_id: Optional[str] = Field(None, description="Impacted CI")
    details: Optional[str] = Field(None, description="Additional context or custom message points")


class CommunicationDraftResponse(BaseModel):
    task_id: Optional[str]
    audience: str
    phase: str
    subject: str
    body_markdown: str
    body_plain: str
    target_channels: List[str]
    next_update_window: str
    approval_required: bool


# ============================================================================
# DEFAULT CMDB TOPOLOGY & REPOSITORY
# ============================================================================

DEFAULT_CMDB_NODES = {
    "ci-cloud-aws-us-east": {
        "ci_id": "ci-cloud-aws-us-east",
        "name": "AWS us-east-1 VPC Infrastructure",
        "type": "Cloud VPC",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "DevOps/SRE",
        "status": "operational",
        "description": "Primary cloud hosting region for all production workloads"
    },
    "ci-k8s-prod-cluster": {
        "ci_id": "ci-k8s-prod-cluster",
        "name": "Production EKS Kubernetes Cluster",
        "type": "Container Platform",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "DevOps/SRE",
        "status": "operational",
        "description": "Primary microservices orchestration platform"
    },
    "ci-kong-api-gateway": {
        "ci_id": "ci-kong-api-gateway",
        "name": "Kong Ingress API Gateway",
        "type": "API Gateway",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "DevOps/SRE",
        "status": "operational",
        "description": "Public reverse proxy and rate-limiting gateway routing all edge traffic"
    },
    "ci-auth-service": {
        "ci_id": "ci-auth-service",
        "name": "User Authentication & SSO Service",
        "type": "Microservice",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "Platform Eng",
        "status": "operational",
        "description": "OAuth2 / JWT token issuer and identity verification service"
    },
    "ci-db-postgres-primary": {
        "ci_id": "ci-db-postgres-primary",
        "name": "PostgreSQL Aurora Primary Cluster",
        "type": "Database",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "Database Team",
        "status": "operational",
        "description": "Master relational database storing accounts, orders, and core transactional state"
    },
    "ci-db-postgres-replica": {
        "ci_id": "ci-db-postgres-replica",
        "name": "PostgreSQL Aurora Read Replica",
        "type": "Database",
        "tier": "Tier 2",
        "environment": "Production",
        "owner_team": "Database Team",
        "status": "operational",
        "description": "Read-only replica for analytics, reporting queries, and search reads"
    },
    "ci-redis-cache": {
        "ci_id": "ci-redis-cache",
        "name": "Redis ElastiCache Cluster",
        "type": "In-Memory Cache",
        "tier": "Tier 2",
        "environment": "Production",
        "owner_team": "DevOps/SRE",
        "status": "operational",
        "description": "Session store, distributed lock manager, and rate limit counters"
    },
    "ci-payment-service": {
        "ci_id": "ci-payment-service",
        "name": "Payment Gateway & Stripe Integration Service",
        "type": "Microservice",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "Payment Ops",
        "status": "operational",
        "description": "Processes customer credit cards, Stripe webhooks, and billing events"
    },
    "ci-order-service": {
        "ci_id": "ci-order-service",
        "name": "Order Management & Checkout Engine",
        "type": "Microservice",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "Platform Eng",
        "status": "operational",
        "description": "Coordinates cart checkout, inventory reservation, and payment capture"
    },
    "ci-inventory-service": {
        "ci_id": "ci-inventory-service",
        "name": "Inventory & Warehouse Catalog Service",
        "type": "Microservice",
        "tier": "Tier 2",
        "environment": "Production",
        "owner_team": "Platform Eng",
        "status": "operational",
        "description": "Tracks stock levels, SKU availability, and warehouse status"
    },
    "ci-notification-service": {
        "ci_id": "ci-notification-service",
        "name": "Customer Notification & Email Worker",
        "type": "Background Worker",
        "tier": "Tier 2",
        "environment": "Production",
        "owner_team": "DevOps/SRE",
        "status": "operational",
        "description": "Sends transactional emails, SMS, and webhook notifications via SendGrid/Twilio"
    },
    "ci-analytics-pipeline": {
        "ci_id": "ci-analytics-pipeline",
        "name": "Kafka & ClickHouse Event Analytics",
        "type": "Data Pipeline",
        "tier": "Tier 3",
        "environment": "Production",
        "owner_team": "Data Platform",
        "status": "operational",
        "description": "Consumes business event streams for BI dashboards and metrics"
    },
    "ci-admin-portal": {
        "ci_id": "ci-admin-portal",
        "name": "Internal Operations Backoffice Portal",
        "type": "Web Application",
        "tier": "Tier 3",
        "environment": "Internal",
        "owner_team": "Platform Eng",
        "status": "operational",
        "description": "Internal employee admin interface for manual overrides and support"
    },
    "ci-customer-web": {
        "ci_id": "ci-customer-web",
        "name": "Next.js Customer Facing Web App",
        "type": "Web Application",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "Platform Eng",
        "status": "operational",
        "description": "Primary consumer web portal at opennow.io"
    },
    "ci-mobile-api": {
        "ci_id": "ci-mobile-api",
        "name": "Mobile BFF (Backend for Frontend) API",
        "type": "API Gateway",
        "tier": "Tier 1",
        "environment": "Production",
        "owner_team": "Platform Eng",
        "status": "operational",
        "description": "Aggregator API serving iOS and Android mobile app clients"
    },
    "ci-elastic-search": {
        "ci_id": "ci-elastic-search",
        "name": "Elasticsearch Centralized Logging Cluster",
        "type": "Log Store",
        "tier": "Tier 2",
        "environment": "Production",
        "owner_team": "DevOps/SRE",
        "status": "operational",
        "description": "Collects Fluentbit log forwarder events and supports search queries"
    }
}

# (Source CI, Target CI, Relationship Type)
# Reading: "Source DEPENDS_ON / RUNS_ON / ROUTES_TO Target"
# Meaning: Source relies on Target!
DEFAULT_CMDB_RELATIONSHIPS = [
    # Infrastructure hosting
    ("ci-k8s-prod-cluster", "ci-cloud-aws-us-east", "hosted_on"),
    ("ci-db-postgres-primary", "ci-cloud-aws-us-east", "hosted_on"),
    ("ci-db-postgres-replica", "ci-cloud-aws-us-east", "hosted_on"),
    ("ci-redis-cache", "ci-cloud-aws-us-east", "hosted_on"),
    ("ci-elastic-search", "ci-cloud-aws-us-east", "hosted_on"),

    # Replication
    ("ci-db-postgres-replica", "ci-db-postgres-primary", "replicates_from"),

    # Services running on Kubernetes
    ("ci-kong-api-gateway", "ci-k8s-prod-cluster", "runs_on"),
    ("ci-auth-service", "ci-k8s-prod-cluster", "runs_on"),
    ("ci-payment-service", "ci-k8s-prod-cluster", "runs_on"),
    ("ci-order-service", "ci-k8s-prod-cluster", "runs_on"),
    ("ci-inventory-service", "ci-k8s-prod-cluster", "runs_on"),
    ("ci-notification-service", "ci-k8s-prod-cluster", "runs_on"),
    ("ci-customer-web", "ci-k8s-prod-cluster", "runs_on"),
    ("ci-admin-portal", "ci-k8s-prod-cluster", "runs_on"),

    # Backend database dependencies
    ("ci-auth-service", "ci-db-postgres-primary", "depends_on"),
    ("ci-auth-service", "ci-redis-cache", "depends_on"),
    ("ci-payment-service", "ci-db-postgres-primary", "depends_on"),
    ("ci-order-service", "ci-db-postgres-primary", "depends_on"),
    ("ci-order-service", "ci-payment-service", "depends_on"),
    ("ci-order-service", "ci-inventory-service", "depends_on"),
    ("ci-inventory-service", "ci-redis-cache", "depends_on"),
    ("ci-notification-service", "ci-redis-cache", "depends_on"),

    # Gateway routing
    ("ci-kong-api-gateway", "ci-auth-service", "routes_to"),
    ("ci-kong-api-gateway", "ci-order-service", "routes_to"),
    ("ci-kong-api-gateway", "ci-payment-service", "routes_to"),

    # Client application dependencies
    ("ci-customer-web", "ci-kong-api-gateway", "depends_on"),
    ("ci-mobile-api", "ci-kong-api-gateway", "depends_on"),
    ("ci-admin-portal", "ci-auth-service", "depends_on"),
    ("ci-admin-portal", "ci-order-service", "depends_on"),

    # Analytics dependencies
    ("ci-analytics-pipeline", "ci-order-service", "consumes_from"),
    ("ci-elastic-search", "ci-k8s-prod-cluster", "ingests_from"),
]


# ============================================================================
# 1. INCIDENT TRIAGE ENGINE
# ============================================================================

class IncidentTriageEngine:
    """
    Intelligently analyzes ticket titles and descriptions to predict:
    - Recommended Priority (P1, P2, P3, P4)
    - Technical Category
    - Assignment Team
    - Sentiment & Urgency (0.0 to 1.0)
    - Identified Configuration Items (CIs)
    - Automated SLA deadlines & Escalation triggers
    """

    CRITICAL_P1_KEYWORDS = {
        "outage", "production down", "prod down", "all users", "complete outage",
        "data loss", "data breach", "ransomware", "zero-day", "exploit",
        "revenue loss", "cannot checkout", "payment failing for all", "stripe down",
        "sev-1", "sev1", "p1", "catastrophic", "blackout", "cluster crash",
        "all pods down", "database corrupt", "deadlock cascade", "500 on all routes",
        "security incident", "unauthorized access", "exfiltration", "site unavailable"
    }

    HIGH_P2_KEYWORDS = {
        "intermittent", "degraded", "high latency", "slowdown", "memory leak",
        "502 bad gateway", "504 gateway timeout", "failover", "queue backlog",
        "disk 95%", "cpu 100%", "high load", "multiple customers", "oomkilled",
        "replication lag", "packet loss", "slow queries", "connection pool",
        "timeout", "spike", "throttling", "rate limit exceeded", "sev-2", "sev2", "p2"
    }

    LOW_P4_KEYWORDS = {
        "typo", "cosmetic", "documentation", "feature request", "how to", "question",
        "sandbox", "test env", "minor ui", "alignment", "color", "label",
        "enhancement", "non-urgent", "when possible", "p4", "sev-4"
    }

    CATEGORY_PATTERNS = {
        "Security": [
            r"\b(breach|vulnerability|exploit|unauthorized|cve|ddos|hacked|token leak|credential|phishing|ransomware|audit log|firewall breach|injection|xss|sql injection)\b"
        ],
        "Database": [
            r"\b(postgres|postgresql|mysql|database|db|query|table|deadlock|replication|aurora|rds|schema|migration|wal|connection pool|pg_stat|index|vacuum)\b"
        ],
        "Payment": [
            r"\b(payment|stripe|billing|invoice|credit card|checkout|charge|refund|transaction|currency|pricing|subscription|payout)\b"
        ],
        "Network": [
            r"\b(dns|vpc|latency|packet loss|route53|cloudflare|cdn|firewall|vpn|subnet|gateway 504|ssl handshake|tls|certificate expired|certbot)\b"
        ],
        "Infrastructure": [
            r"\b(kubernetes|k8s|eks|pod|node|cpu spike|memory leak|oom|oomkilled|crashloopbackoff|aws|ec2|s3|docker|container|ingress|daemonset)\b"
        ],
        "Access": [
            r"\b(login|sso|okta|permission|access denied|403 forbidden|password reset|mfa|auth0|role|privilege|account locked)\b"
        ],
        "Application": [
            r"\b(frontend|react|nextjs|ui|button|null pointer|exception|unhandled|traceback|api 500|endpoint|json parse|view|client)\b"
        ]
    }

    TEAM_MAPPINGS = {
        "Security": "SecOps",
        "Database": "Database Team",
        "Infrastructure": "DevOps/SRE",
        "Network": "DevOps/SRE",
        "Payment": "Payment Ops",
        "Access": "Tier 1 Support",
        "Application": "Platform Eng"
    }

    URGENT_PHRASES = {
        "immediately": 0.25,
        "asap": 0.20,
        "blocking all": 0.35,
        "executive": 0.25,
        "vp": 0.20,
        "ceo": 0.30,
        "critical": 0.25,
        "emergency": 0.30,
        "sla breach": 0.30,
        "revenue": 0.25,
        "customers screaming": 0.30,
        "prod": 0.15,
        "production": 0.20,
        "escalate": 0.25,
    }

    DISTRESS_WORDS = {
        "unacceptable": -0.30,
        "disaster": -0.35,
        "broken": -0.20,
        "furious": -0.40,
        "embarrassing": -0.30,
        "failing": -0.20,
        "down": -0.15,
        "terrible": -0.30,
        "stuck": -0.15,
        "severe": -0.25,
        "outage": -0.25,
        "frustrated": -0.30,
    }

    POSITIVE_WORDS = {
        "thanks": 0.15,
        "please": 0.10,
        "appreciate": 0.15,
        "resolved": 0.20,
        "working": 0.15,
        "good": 0.10,
        "helpful": 0.15
    }

    def __init__(self, cmdb_nodes: Optional[Dict[str, Dict[str, Any]]] = None):
        self.cmdb_nodes = cmdb_nodes or DEFAULT_CMDB_NODES

    def triage(self, request: TriageRequest) -> TriageResponse:
        full_text = f"{request.title} {request.description}".lower()
        reasoning: List[str] = []

        # 1. Identify CIs mentioned in text
        identified_cis = self._extract_cis(full_text)
        if identified_cis:
            ci_names = [ci["name"] for ci in identified_cis]
            reasoning.append(f"Identified configuration items referenced in ticket: {', '.join(ci_names)}")

        # 2. Predict Category
        category = self._predict_category(full_text)
        reasoning.append(f"Classified category as '{category}' from technical keyword signatures.")

        # 3. Predict Urgency and Sentiment
        urgency_score = self._compute_urgency(full_text)
        sentiment_score, sentiment_label = self._compute_sentiment(full_text)

        # 4. Predict Priority
        priority_code, priority_label, prio_reasons = self._predict_priority(
            full_text, category, urgency_score, identified_cis
        )
        reasoning.extend(prio_reasons)

        # 5. Determine Assignment Team
        team = self._determine_assignment_team(category, identified_cis)
        reasoning.append(f"Routed to primary escalation team: '{team}'")

        # 6. SLA Calculations
        sla_resp, sla_reso = self._compute_slas(priority_code)

        # 7. Escalation Rules
        escalation_triggered = False
        escalation_action = None
        if priority_code == "P1" or urgency_score >= 0.85:
            escalation_triggered = True
            escalation_action = (
                f"P1 Major Incident: Auto-spin Incident Command Bridge, page {team} on-call lead, "
                f"and broadcast incident alert to executive dashboard."
            )
            reasoning.append("High urgency/P1 trigger: Automated on-call escalation executed.")
        elif category == "Security":
            escalation_triggered = True
            escalation_action = "Security Incident Protocol: Auto-restricted ticket ACL and paged SecOps Commander."
            reasoning.append("Security trigger: SecOps priority protocol engaged.")

        # 8. Impact Scope
        impact_scope = "Localized"
        if priority_code == "P1":
            impact_scope = "Enterprise-wide"
        elif priority_code == "P2":
            impact_scope = "Multi-service"
        elif priority_code == "P3":
            impact_scope = "Single-service"

        # 9. Smart Tags
        tags = [category.lower(), priority_code.lower()]
        if identified_cis:
            tags.extend([ci["ci_id"] for ci in identified_cis])
        if escalation_triggered:
            tags.append("auto-escalated")
        if urgency_score > 0.7:
            tags.append("high-urgency")

        return TriageResponse(
            task_id=request.task_id,
            title=request.title,
            recommended_priority=priority_label,
            priority_code=priority_code,
            category=category,
            recommended_assignment_team=team,
            urgency_score=round(urgency_score, 2),
            sentiment_score=round(sentiment_score, 2),
            sentiment_label=sentiment_label,
            identified_cis=identified_cis,
            impact_scope=impact_scope,
            sla_response_target=sla_resp,
            sla_resolution_target=sla_reso,
            escalation_triggered=escalation_triggered,
            escalation_action=escalation_action,
            tags=tags,
            reasoning_summary=reasoning
        )

    def _extract_cis(self, text: str) -> List[Dict[str, Any]]:
        scored_matches: List[Tuple[int, Dict[str, Any]]] = []
        for ci_id, ci_data in self.cmdb_nodes.items():
            name_lower = ci_data["name"].lower()
            ci_id_lower = ci_id.lower()
            score = 0
            if len(ci_id_lower) >= 4 and not ci_id_lower.isdigit():
                if ci_id_lower in text:
                    score += 100
            elif ci_id_lower.isdigit():
                if re.search(rf"\b(ci[-_ ]?#{ci_id_lower}|ci[-_ ]{ci_id_lower}|ci:{ci_id_lower})\b", text):
                    score += 100
            else:
                if re.search(rf"\b{re.escape(ci_id_lower)}\b", text):
                    score += 100

            if len(name_lower) >= 4 and name_lower in text:
                score += 80

            # Distinct service keywords
            if "auth service" in text or "authentication service" in text or "auth" in text or "jwt" in text or "login" in text:
                if ci_id == "ci-auth-service":
                    score += 70
            if "payment" in text or "stripe" in text or "checkout" in text:
                if ci_id == "ci-payment-service":
                    score += 70
            if "postgres" in text or "aurora" in text or "deadlock" in text or "database" in text:
                if ci_id == "ci-db-postgres-primary":
                    score += 65
            if "order service" in text or "checkout engine" in text:
                if ci_id == "ci-order-service":
                    score += 60
            if "kong" in text or "api gateway" in text:
                if ci_id == "ci-kong-api-gateway":
                    score += 60
            if "redis" in text or "cache" in text:
                if ci_id == "ci-redis-cache":
                    score += 50
            if "kubernetes" in text or "eks" in text or "k8s cluster" in text:
                if ci_id == "ci-k8s-prod-cluster":
                    score += 50
            elif "pod" in text or "container" in text or "k8s" in text:
                if ci_id == "ci-k8s-prod-cluster":
                    score += 15  # Generic container level mention

            if score > 0:
                scored_matches.append((score, ci_data))

        # Sort by score descending
        scored_matches.sort(key=lambda x: x[0], reverse=True)

        seen = set()
        deduped = []
        for _, ci in scored_matches:
            if ci["ci_id"] not in seen:
                seen.add(ci["ci_id"])
                deduped.append(ci)
        return deduped

    def _predict_category(self, text: str) -> str:
        scores: Dict[str, int] = {cat: 0 for cat in self.CATEGORY_PATTERNS}
        for cat, patterns in self.CATEGORY_PATTERNS.items():
            for pat in patterns:
                found = re.findall(pat, text, re.IGNORECASE)
                scores[cat] += len(found) * 2

        # Special contextual boosters
        if "postgres" in text or "query" in text or "deadlock" in text or "sql" in text:
            scores["Database"] += 3
        if "stripe" in text or "payment" in text or "billing" in text or "checkout" in text:
            scores["Payment"] += 3
        if "k8s" in text or "kubernetes" in text or "pod" in text or "oom" in text:
            scores["Infrastructure"] += 3
        if "breach" in text or "cve" in text or "exploit" in text or "unauthorized" in text:
            scores["Security"] += 5
        if "sso" in text or "login" in text or "okta" in text or "permission" in text:
            scores["Access"] += 3
        if "dns" in text or "route53" in text or "latency" in text or "ssl" in text or "tls" in text:
            scores["Network"] += 3

        best_cat = max(scores.items(), key=lambda x: x[1])
        return best_cat[0] if best_cat[1] > 0 else "Application"

    def _compute_urgency(self, text: str) -> float:
        base_urgency = 0.35
        for phrase, weight in self.URGENT_PHRASES.items():
            if phrase in text:
                base_urgency += weight
        return min(max(base_urgency, 0.05), 1.0)

    def _compute_sentiment(self, text: str) -> Tuple[float, str]:
        score = 0.65  # Base neutral/calm default
        for word, val in self.DISTRESS_WORDS.items():
            if word in text:
                score += val
        for word, val in self.POSITIVE_WORDS.items():
            if word in text:
                score += val
        
        score = max(min(score, 1.0), 0.0)
        if score <= 0.25:
            label = "Critical Distress"
        elif score <= 0.45:
            label = "Frustrated"
        elif score <= 0.70:
            label = "Neutral"
        else:
            label = "Calm"
        return score, label

    def _predict_priority(
        self, text: str, category: str, urgency: float, identified_cis: List[Dict[str, Any]]
    ) -> Tuple[str, str, List[str]]:
        reasons = []
        
        # Check P1 conditions
        has_p1_keyword = any(kw in text for kw in self.CRITICAL_P1_KEYWORDS)
        has_tier1_ci = any(ci.get("tier") == "Tier 1" for ci in identified_cis)
        
        if has_p1_keyword or (urgency >= 0.80 and has_tier1_ci):
            reasons.append("P1-Critical assigned: Detected widespread outage keywords, core service impact, or critical revenue/security severity.")
            return "P1", "P1-Critical", reasons

        # Check P4 conditions
        has_p4_keyword = any(kw in text for kw in self.LOW_P4_KEYWORDS)
        if has_p4_keyword and urgency < 0.40 and not has_tier1_ci:
            reasons.append("P4-Low assigned: Ticket relates to minor cosmetic defect, documentation request, or sandbox environment.")
            return "P4", "P4-Low", reasons

        # Check P2 conditions
        has_p2_keyword = any(kw in text for kw in self.HIGH_P2_KEYWORDS)
        if has_p2_keyword or urgency >= 0.60 or category in ("Database", "Payment", "Security"):
            reasons.append("P2-High assigned: Performance degradation, intermittent errors, or sensitive business domain impact detected.")
            return "P2", "P2-High", reasons

        # Default Moderate
        reasons.append("P3-Moderate assigned: Standard priority for isolated defect with workaround available.")
        return "P3", "P3-Moderate", reasons

    def _determine_assignment_team(self, category: str, cis: List[Dict[str, Any]]) -> str:
        # Specialized domains route directly to expert response teams
        if category in ("Security", "Database", "Payment", "Access"):
            return self.TEAM_MAPPINGS.get(category, "DevOps/SRE")
        # If specific CI owner is known, route to CI owner
        if cis:
            primary_ci = cis[0]
            if primary_ci.get("owner_team"):
                return primary_ci["owner_team"]
        return self.TEAM_MAPPINGS.get(category, "DevOps/SRE")

    def _compute_slas(self, priority_code: str) -> Tuple[str, str]:
        sla_table = {
            "P1": ("15 minutes", "1 hour"),
            "P2": ("30 minutes", "4 hours"),
            "P3": ("2 hours", "24 hours"),
            "P4": ("8 hours", "72 hours")
        }
        return sla_table.get(priority_code, ("1 hour", "8 hours"))


# ============================================================================
# 2. CMDB BLAST RADIUS & ROOT CAUSE ENGINE
# ============================================================================

class CMDBBlastRadiusEngine:
    """
    Traverses the CMDB dependency graph to determine:
    1. Upstream Dependencies: What this service relies on (inbound root-cause candidates).
    2. Downstream Blast Radius: What other services, APIs, and business operations will fail.
    3. System Risk Score: 0-100 composite risk calculation based on CI criticality and downstream fanout.
    """

    def __init__(
        self,
        nodes: Optional[Dict[str, Dict[str, Any]]] = None,
        relationships: Optional[List[Tuple[str, str, str]]] = None
    ):
        self.nodes = nodes or DEFAULT_CMDB_NODES
        # relationships: list of (Source, Target, Type) where Source DEPENDS_ON Target
        self.relationships = relationships or DEFAULT_CMDB_RELATIONSHIPS
        
        # Build directed graph adjacencies
        # forward_dep[A] = [B, ...] -> A depends on B (B is upstream to A)
        # reverse_dep[B] = [A, ...] -> A depends on B (A is downstream of B, will break if B fails!)
        self.upstream_graph: Dict[str, List[Tuple[str, str]]] = {k: [] for k in self.nodes}
        self.downstream_graph: Dict[str, List[Tuple[str, str]]] = {k: [] for k in self.nodes}

        for src, tgt, rel in self.relationships:
            if src in self.upstream_graph and tgt in self.nodes:
                self.upstream_graph[src].append((tgt, rel))
            if tgt in self.downstream_graph and src in self.nodes:
                self.downstream_graph[tgt].append((src, rel))

    def _import_from_db(self) -> None:
        """Syncs in-memory CMDB graph with SQLite database if populated."""
        try:
            from backend.database import db
            graph = db.get_cmdb_graph()
            for n in graph.get("nodes", []):
                nid = str(n["id"])
                tier_str = f"Tier {n.get('tier', 2)}"
                if nid not in self.nodes:
                    self.nodes[nid] = {
                        "ci_id": nid,
                        "name": n.get("name", nid),
                        "type": n.get("ci_type", "Service"),
                        "tier": tier_str,
                        "environment": n.get("environment", "Production"),
                        "owner_team": n.get("owner_team", "DevOps/SRE"),
                        "status": n.get("health_status", "operational"),
                        "description": f"Imported from OpenNow DB (ID: {n['id']})"
                    }
                    self.upstream_graph[nid] = []
                    self.downstream_graph[nid] = []
            
            for e in graph.get("edges", []):
                src = str(e["source"])
                tgt = str(e["target"])
                rel = e.get("relationship_type", "depends_on")
                if src in self.upstream_graph and tgt in self.nodes:
                    if (tgt, rel) not in self.upstream_graph[src]:
                        self.upstream_graph[src].append((tgt, rel))
                if tgt in self.downstream_graph and src in self.nodes:
                    if (src, rel) not in self.downstream_graph[tgt]:
                        self.downstream_graph[tgt].append((src, rel))
        except Exception:
            pass

    CI_ALIASES = {
        "ci-db-001": "ci-db-postgres-primary",
        "ci-cache-002": "ci-redis-cache",
        "ci-pay-003": "ci-payment-service",
        "ci-auth-004": "ci-auth-service",
        "ci-ingress-005": "ci-kong-api-gateway",
        "ci-k8s-006": "ci-k8s-prod-cluster",
        "ci-kafka-007": "ci-analytics-pipeline",
        "ci-cdn-008": "ci-cloud-aws-us-east",
    }

    def _resolve_node_id(self, ci_id: Any) -> str:
        ci_str = str(ci_id).strip()
        if ci_str.lower() in self.CI_ALIASES:
            return self.CI_ALIASES[ci_str.lower()]

        if ci_str in self.nodes:
            return ci_str
        
        # Check by name or case-insensitive match
        for k, v in self.nodes.items():
            if k.lower() == ci_str.lower() or v.get("name", "").lower() == ci_str.lower():
                return k

        # Try to pull from database
        try:
            self._import_from_db()
            if ci_str in self.nodes:
                return ci_str
            for k, v in self.nodes.items():
                if k.lower() == ci_str.lower() or v.get("name", "").lower() == ci_str.lower():
                    return k
        except Exception:
            pass

        return ci_str

    def analyze_blast_radius(self, request: BlastRadiusRequest) -> BlastRadiusResponse:
        ci_id = self._resolve_node_id(request.ci_id)
        if ci_id not in self.nodes:
            # Fallback for unknown CI: create a synthetic node
            self.nodes[ci_id] = {
                "ci_id": ci_id,
                "name": f"Dynamic CI ({ci_id})",
                "type": "Custom Resource",
                "tier": "Tier 2",
                "environment": "Production",
                "owner_team": "DevOps/SRE",
                "status": "operational",
                "description": "Dynamically registered configuration item"
            }
            self.upstream_graph[ci_id] = []
            self.downstream_graph[ci_id] = []

        target_node = self.nodes[ci_id]

        # 1. Compute Downstream Blast Radius (Nodes that depend on target_ci)
        downstream_nodes = self._traverse_graph(ci_id, self.downstream_graph, request.max_depth or 5)

        # 2. Compute Upstream Dependencies (Nodes target_ci relies on)
        upstream_nodes = self._traverse_graph(ci_id, self.upstream_graph, request.max_depth or 5)

        # 3. Calculate Risk Score
        risk_score, risk_level = self._calculate_risk_score(target_node, downstream_nodes)

        # 4. Synthesize Business Impact Summary
        direct_count = len([d for d in downstream_nodes if d.cascade_depth == 1])
        tier1_count = len([d for d in downstream_nodes if d.tier == "Tier 1"])
        max_depth = max([d.cascade_depth for d in downstream_nodes], default=0)

        critical_ops = self._extract_critical_business_operations(downstream_nodes, target_node)
        biz_summary = self._generate_impact_summary(
            target_node, downstream_nodes, direct_count, tier1_count, risk_level, critical_ops
        )

        containment_recommendations = self._generate_containment_actions(target_node, downstream_nodes)

        return BlastRadiusResponse(
            target_ci=target_node,
            upstream_dependencies=upstream_nodes,
            downstream_blast_radius=downstream_nodes,
            cascade_depth=max_depth,
            direct_dependents_count=direct_count,
            total_impacted_services=len(downstream_nodes),
            impacted_tier_1_count=tier1_count,
            system_risk_score=risk_score,
            risk_level=risk_level,
            business_impact_summary=biz_summary,
            critical_business_operations=critical_ops,
            recommended_containment=containment_recommendations
        )

    def _traverse_graph(
        self, start_id: str, graph: Dict[str, List[Tuple[str, str]]], max_depth: int
    ) -> List[CIRef]:
        visited: Set[str] = set()
        results: List[CIRef] = []
        queue: deque[Tuple[str, int, str]] = deque()

        # Enqueue direct neighbors
        for neighbor, rel in graph.get(start_id, []):
            queue.append((neighbor, 1, rel))
            visited.add(neighbor)

        while queue:
            curr_id, depth, rel = queue.popleft()
            if depth > max_depth:
                continue

            node_data = self.nodes.get(curr_id, {})
            results.append(
                CIRef(
                    ci_id=curr_id,
                    name=node_data.get("name", curr_id),
                    type=node_data.get("type", "Unknown"),
                    tier=node_data.get("tier", "Tier 3"),
                    environment=node_data.get("environment", "Production"),
                    owner_team=node_data.get("owner_team", "DevOps/SRE"),
                    cascade_depth=depth,
                    relationship_type=rel,
                    status=node_data.get("status", "operational")
                )
            )

            # Traverse further
            for next_node, next_rel in graph.get(curr_id, []):
                if next_node not in visited and next_node != start_id:
                    visited.add(next_node)
                    queue.append((next_node, depth + 1, next_rel))

        return results

    def _calculate_risk_score(
        self, target_node: Dict[str, Any], downstream_nodes: List[CIRef]
    ) -> Tuple[int, str]:
        # Base weight from target CI Tier
        tier = target_node.get("tier", "Tier 2")
        base_weights = {"Tier 1": 45, "Tier 2": 25, "Tier 3": 10}
        score = base_weights.get(tier, 20)

        # Factor in downstream nodes
        for node in downstream_nodes:
            if node.tier == "Tier 1":
                score += 12
            elif node.tier == "Tier 2":
                score += 6
            else:
                score += 2

        # Depth cascade factor
        max_depth = max([n.cascade_depth for n in downstream_nodes], default=0)
        if max_depth >= 3:
            score += 15
        elif max_depth >= 2:
            score += 8

        # Cap score between 0 and 100
        score = min(max(score, 5), 100)

        if score >= 80:
            level = "CRITICAL"
        elif score >= 60:
            level = "HIGH"
        elif score >= 35:
            level = "MEDIUM"
        else:
            level = "LOW"

        return score, level

    def _extract_critical_business_operations(
        self, downstream_nodes: List[CIRef], target_node: Dict[str, Any]
    ) -> List[str]:
        ops = set()
        all_cis = [target_node.get("ci_id", "")] + [n.ci_id for n in downstream_nodes]
        all_names = [target_node.get("name", "").lower()] + [n.name.lower() for n in downstream_nodes]

        text_block = " ".join(all_cis + all_names).lower()

        if "payment" in text_block or "stripe" in text_block or "order" in text_block:
            ops.add("Customer Checkout & Revenue Processing")
        if "auth" in text_block or "sso" in text_block or "login" in text_block:
            ops.add("User Authentication & Session Management")
        if "customer-web" in text_block or "mobile-api" in text_block or "kong" in text_block:
            ops.add("Public Customer Portal & Mobile App Availability")
        if "notification" in text_block:
            ops.add("Transactional Email & SMS Delivery")
        if "admin-portal" in text_block:
            ops.add("Internal Backoffice Operations & Support Management")
        if "analytics" in text_block:
            ops.add("Business Intelligence & Metrics Stream Ingestion")

        if not ops:
            ops.add("General Application Operations")

        return sorted(list(ops))

    def _generate_impact_summary(
        self,
        target_node: Dict[str, Any],
        downstream: List[CIRef],
        direct_count: int,
        tier1_count: int,
        risk_level: str,
        ops: List[str]
    ) -> str:
        name = target_node.get("name", target_node.get("ci_id"))
        tier = target_node.get("tier", "Tier 2")

        if not downstream:
            return (
                f"Degradation or outage of {name} ({tier}) represents an isolated event with NO direct downstream "
                f"microservices or web applications affected. Risk level is {risk_level}."
            )

        return (
            f"Failure of {name} ({tier}) triggers a {risk_level} blast radius impacting {len(downstream)} downstream "
            f"components ({direct_count} direct, {tier1_count} mission-critical Tier 1 services). "
            f"Key business capabilities at immediate risk: {', '.join(ops)}."
        )

    def _generate_containment_actions(
        self, target_node: Dict[str, Any], downstream: List[CIRef]
    ) -> List[str]:
        actions = []
        target_type = target_node.get("type", "").lower()
        ci_id = target_node.get("ci_id", "")

        if "database" in target_type or "postgres" in ci_id:
            actions.append("Engage database read-replica failover or scale read-only pools to relieve primary pressure.")
            actions.append("Activate database circuit breakers on Order and Payment microservices to prevent thread exhaustion.")
        elif "gateway" in target_type or "kong" in ci_id:
            actions.append("Enable Cloudflare edge rate-limiting and divert non-essential traffic to static maintenance page.")
            actions.append("Spin up redundant gateway pods across alternative availability zones.")
        elif "payment" in ci_id:
            actions.append("Switch payment gateway provider to secondary failover processor.")
            actions.append("Queue pending customer checkouts with asynchronous processing notice to prevent basket abandonment.")
        elif "cache" in target_type or "redis" in ci_id:
            actions.append("Enable local in-memory fallback cache on Auth and Inventory services to survive Redis downtime.")
        else:
            actions.append(f"Isolate {target_node.get('name', ci_id)} and verify health probes on immediate dependents.")

        actions.append("Notify on-call incident commanders of upstream and downstream dependent team leads.")
        return actions


# ============================================================================
# 3. RUNBOOK SYNTHESIZER
# ============================================================================

class RunbookSynthesizer:
    """
    Generates step-by-step diagnostic CLI commands, verification scripts, and
    remediation runbooks tailored to specific ITIL/SRE incident patterns:
    - Postgres Connection Pool / Deadlock
    - Kubernetes Pod CrashLoopBackOff & Out-Of-Memory (OOM)
    - SSL/TLS Certificate Expiry & Renewal
    - Payment Gateway Webhook / Ingestion Failures
    - High Network Latency / DNS Timeout
    - Generic SRE Incident Diagnostic Lifecycle
    """

    def synthesize(self, request: RunbookRequest) -> RunbookResponse:
        title = (request.title or "").lower()
        desc = (request.description or "").lower()
        cat = (request.category or "").lower()
        ci = (request.ci_id or "").lower()

        combined = f"{title} {desc} {cat} {ci}"

        # Match specific runbooks
        if "postgres" in combined or "deadlock" in combined or "lock" in combined or "db" in combined:
            return self._build_postgres_runbook(request)
        elif "crashloop" in combined or "k8s" in combined or "pod" in combined or "kubernetes" in combined:
            return self._build_k8s_crashloop_runbook(request)
        elif "memory" in combined or "oom" in combined or "leak" in combined:
            return self._build_oom_memory_runbook(request)
        elif "ssl" in combined or "cert" in combined or "tls" in combined or "expired" in combined:
            return self._build_ssl_renewal_runbook(request)
        elif "payment" in combined or "stripe" in combined or "billing" in combined:
            return self._build_payment_gateway_runbook(request)
        elif "dns" in combined or "latency" in combined or "timeout" in combined:
            return self._build_network_dns_runbook(request)
        else:
            return self._build_generic_runbook(request)

    def _build_postgres_runbook(self, request: RunbookRequest) -> RunbookResponse:
        steps = [
            RunbookStep(
                step_number=1,
                phase="Diagnostic",
                title="Inspect Active Connection Pool Usage & Client States",
                description="Query pg_stat_activity to determine current connection count, state breakdown, and active clients.",
                command=(
                    "SELECT state, count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() GROUP BY state ORDER BY count DESC;"
                ),
                expected_output="Normal state: <80% max_connections, majority 'idle'. Alert: >95% active or 'idle in transaction'."
            ),
            RunbookStep(
                step_number=2,
                phase="Diagnostic",
                title="Identify Blocking Locks and Deadlock Chains",
                description="Find queries holding exclusive table/tuple locks that are blocking incoming write transactions.",
                command=(
                    "SELECT blocked_locks.pid AS blocked_pid, blocking_locks.pid AS blocking_pid, "
                    "blocked_activity.query AS blocked_statement, blocking_activity.query AS current_statement_in_blocking_process "
                    "FROM pg_catalog.pg_locks blocked_locks "
                    "JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid "
                    "JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype "
                    "AND blocking_locks.pid != blocked_locks.pid "
                    "JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid "
                    "WHERE NOT blocked_locks.granted LIMIT 10;"
                ),
                expected_output="PIDs and SQL statements causing cascade contention."
            ),
            RunbookStep(
                step_number=3,
                phase="Containment",
                title="Gracefully Cancel Blocking Process",
                description="Issue pg_cancel_backend to request gentle cancellation of the rogue or stuck transaction.",
                command="SELECT pg_cancel_backend(<BLOCKING_PID>);",
                safety_warning="Ensure you are targeting the blocker PID, not the worker threads waiting for the lock."
            ),
            RunbookStep(
                step_number=4,
                phase="Remediation",
                title="Force Terminate Stuck Process (If Cancellation Times Out)",
                description="If pg_cancel_backend does not release the lock within 20 seconds, terminate the backend server process.",
                command="SELECT pg_terminate_backend(<BLOCKING_PID>);",
                safety_warning="This will drop the TCP session for that specific client connection."
            ),
            RunbookStep(
                step_number=5,
                phase="Remediation",
                title="Recycle Application Connection Poolers (PgBouncer)",
                description="Flush drained or zombie pooled sockets by triggering a graceful reload of PgBouncer pods.",
                command="kubectl rollout restart deployment/pgbouncer -n database",
                expected_output="deployment.apps/pgbouncer restarted successfully."
            ),
            RunbookStep(
                step_number=6,
                phase="Verification",
                title="Verify Pool Health and Query Response Latency",
                description="Check database transaction duration and verify API latency returns to p95 < 50ms baseline.",
                command="SELECT max(now() - query_start) as max_query_age FROM pg_stat_activity WHERE state = 'active';",
                expected_output="max_query_age should drop to < 2 seconds."
            )
        ]

        return RunbookResponse(
            task_id=request.task_id,
            runbook_id="RB-DB-POSTGRES-LOCK-01",
            runbook_title="PostgreSQL Aurora Lock Contention & Connection Exhaustion Remediation",
            category="Database",
            target_ci=request.ci_id or "ci-db-postgres-primary",
            estimated_duration="10 - 20 minutes",
            prerequisites=[
                "Read/Write access to PostgreSQL master cluster via psql or AWS RDS Bastion",
                "Kubernetes kubectl CLI configured for production cluster",
                "DBA or SRE on-call elevation privileges"
            ],
            diagnostic_commands=[
                "psql -h $PG_HOST -U $PG_USER -d $PG_DB -c 'SHOW max_connections;'",
                "psql -h $PG_HOST -U $PG_USER -d $PG_DB -c 'SELECT count(*) FROM pg_stat_activity;'",
                "curl -sSf http://api.opennow.io/health/db | jq ."
            ],
            steps=steps,
            verification_steps=[
                "Confirm active connection count is below 70% threshold",
                "Verify no ungranted locks remain in pg_catalog.pg_locks",
                "Validate API gateway 5xx error rate returns to zero in Grafana/CloudWatch"
            ],
            rollback_plan=[
                "If Aurora primary becomes completely unresponsive, trigger automated multi-AZ failover via AWS RDS console: 'aws rds failover-db-cluster --db-cluster-identifier prod-aurora-cluster'"
            ],
            safety_notes=[
                "Never execute 'TRUNCATE' or 'DROP TABLE' during active connection contention",
                "Avoid restarting the entire database node unless failover is planned and coordinated"
            ]
        )

    def _build_k8s_crashloop_runbook(self, request: RunbookRequest) -> RunbookResponse:
        steps = [
            RunbookStep(
                step_number=1,
                phase="Diagnostic",
                title="Inspect Failing Pod State & Termination Reason",
                description="Run kubectl describe on the affected pod to inspect Exit Codes, Liveness Probe failures, and events.",
                command="kubectl describe pod -l app=<APP_NAME> -n production",
                expected_output="Inspect 'Last State' (e.g. Exit Code 1, 137 OOMKilled, or 139 SegFault)."
            ),
            RunbookStep(
                step_number=2,
                phase="Diagnostic",
                title="Fetch Crashed Container Previous Logs",
                description="View standard output and stack traces from the container crash immediately prior to termination.",
                command="kubectl logs -l app=<APP_NAME> -n production --previous --tail=100",
                expected_output="Fatal stack trace, uncaught exception, or missing environment variable."
            ),
            RunbookStep(
                step_number=3,
                phase="Containment",
                title="Verify ConfigMaps and Vault Secrets",
                description="Ensure required database credentials, API tokens, and ConfigMap keys are mounted and not corrupted.",
                command="kubectl get configmap <APP_CONFIG> -n production -o yaml",
                expected_output="Valid YAML syntax and non-empty environment values."
            ),
            RunbookStep(
                step_number=4,
                phase="Remediation",
                title="Rollback Recent Faulty Deployment",
                description="If failure started after a recent CI/CD rollout, roll back to the previous stable ReplicaSet revision.",
                command="kubectl rollout undo deployment/<DEPLOYMENT_NAME> -n production",
                expected_output="deployment.apps/<DEPLOYMENT_NAME> rolled back."
            ),
            RunbookStep(
                step_number=5,
                phase="Verification",
                title="Monitor Pod Rollout and Health Check Probes",
                description="Watch pods achieve 1/1 Running state and pass initial HTTP readiness probes.",
                command="kubectl rollout status deployment/<DEPLOYMENT_NAME> -n production --timeout=90s",
                expected_output="deployment successfully rolled out with all replicas ready."
            )
        ]

        return RunbookResponse(
            task_id=request.task_id,
            runbook_id="RB-K8S-CRASHLOOP-02",
            runbook_title="Kubernetes Pod CrashLoopBackOff Diagnostic & Rollback Runbook",
            category="Infrastructure",
            target_ci=request.ci_id or "ci-k8s-prod-cluster",
            estimated_duration="10 - 15 minutes",
            prerequisites=[
                "kubectl access with cluster-admin or deployment-write role in production namespace",
                "Access to Datadog/Grafana container telemetry"
            ],
            diagnostic_commands=[
                "kubectl get pods -n production --field-selector=status.phase!=Running",
                "kubectl get events -n production --sort-by='.lastTimestamp' | tail -20"
            ],
            steps=steps,
            verification_steps=[
                "Run 'kubectl get pods -n production' and verify 0 restarts over 5 minutes",
                "Execute HTTP curl against health probe endpoint: 'curl -I http://<service>/healthz'"
            ],
            rollback_plan=[
                "If rollback fails, scale deployment to zero and re-deploy known stable tag from ECR container registry."
            ],
            safety_notes=[
                "Do not delete persistent volume claims (PVCs) while troubleshooting pod restarts",
                "Always check '--previous' logs before deleting crashed pods to preserve diagnostic evidence"
            ]
        )

    def _build_oom_memory_runbook(self, request: RunbookRequest) -> RunbookResponse:
        steps = [
            RunbookStep(
                step_number=1,
                phase="Diagnostic",
                title="Inspect Memory Utilization and OOM Events",
                description="Check node and pod memory usage against configured limits.",
                command="kubectl top pods -n production --sort-by=memory | head -10",
                expected_output="Pods consuming >90% of memory limit."
            ),
            RunbookStep(
                step_number=2,
                phase="Diagnostic",
                title="Examine Linux Kernel dmesg Out-Of-Memory Kills",
                description="Verify if Linux cgroup memory subsystem killed process with signal 9.",
                command="dmesg -T | grep -E -i 'oom[- ]killer|killed process' | tail -10",
                expected_output="Kernel OOM log indicating process and memory invocation limits."
            ),
            RunbookStep(
                step_number=3,
                phase="Containment",
                title="Temporarily Elevate Memory Limit Ceiling",
                description="Patch deployment resource limits to provide immediate buffer against crash cycling.",
                command=(
                    "kubectl set resources deployment <DEPLOYMENT_NAME> -n production "
                    "--limits=memory=4Gi --requests=memory=2Gi"
                ),
                safety_warning="Confirm host nodes have sufficient spare memory allocatable before patching."
            ),
            RunbookStep(
                step_number=4,
                phase="Remediation",
                title="Trigger Rolling Pod Restart to Flush Leaked Heap Memory",
                description="Perform a zero-downtime rolling restart to recycle worker processes with clean heaps.",
                command="kubectl rollout restart deployment/<DEPLOYMENT_NAME> -n production",
                expected_output="Rolling restart completed."
            ),
            RunbookStep(
                step_number=5,
                phase="Verification",
                title="Continuously Profile RSS Memory Growth",
                description="Monitor Resident Set Size (RSS) slope in Prometheus/Grafana to ensure stable flatline.",
                command="kubectl top pod -l app=<APP_NAME> -n production",
                expected_output="Memory consumption stabilizes below 50% limit."
            )
        ]

        return RunbookResponse(
            task_id=request.task_id,
            runbook_id="RB-INFRA-OOM-03",
            runbook_title="Memory Leak & Container OOMKilled Emergency Remediation",
            category="Infrastructure",
            target_ci=request.ci_id or "ci-k8s-prod-cluster",
            estimated_duration="15 - 20 minutes",
            prerequisites=["kubectl access", "Prometheus/Grafana memory telemetry access"],
            diagnostic_commands=[
                "kubectl top nodes",
                "kubectl top pods -A --sort-by=memory | head -20"
            ],
            steps=steps,
            verification_steps=[
                "Verify no OOM events in 'kubectl get events -n production | grep OOM'",
                "Confirm node memory allocatable is > 20% across all EKS nodes"
            ],
            rollback_plan=[
                "Revert patched resource limits back to GitOps specification once heap profiler identifies leaking module"
            ],
            safety_notes=[
                "Increasing memory limits is a temporary containment measure, not a permanent fix for code-level leaks"
            ]
        )

    def _build_ssl_renewal_runbook(self, request: RunbookRequest) -> RunbookResponse:
        steps = [
            RunbookStep(
                step_number=1,
                phase="Diagnostic",
                title="Inspect Live TLS Certificate Expiry & Serial",
                description="Probe the external domain with OpenSSL to inspect certificate valid dates and Subject Alternative Names.",
                command="openssl s_client -connect opennow.io:443 -servername opennow.io </dev/null 2>/dev/null | openssl x509 -noout -dates -subject -issuer",
                expected_output="notAfter date and issuing authority (e.g. Let's Encrypt / DigiCert)."
            ),
            RunbookStep(
                step_number=2,
                phase="Diagnostic",
                title="Check cert-manager Certificate & Order Status",
                description="Inspect Kubernetes cert-manager CRDs for renewal challenges or ACME DNS validation blocks.",
                command="kubectl describe certificate opennow-tls -n production",
                expected_output="Status: Ready=False, Message explaining ACME challenge state."
            ),
            RunbookStep(
                step_number=3,
                phase="Remediation",
                title="Trigger Manual ACME Certificate Renewal",
                description="Instruct cert-manager or certbot to initiate immediate challenge re-validation.",
                command="kubectl cert-manager renew opennow-tls -n production",
                expected_output="Certificate renewal order triggered."
            ),
            RunbookStep(
                step_number=4,
                phase="Remediation",
                title="Reload Ingress & Reverse Proxy TLS Cache",
                description="Restart ingress controllers to force them to reload the new TLS secret from Kubernetes.",
                command="kubectl rollout restart deployment/kong-ingress-controller -n ingress",
                expected_output="Ingress controller restarted."
            ),
            RunbookStep(
                step_number=5,
                phase="Verification",
                title="Verify SSL Handshake Globally",
                description="Perform live curl and SSL test to confirm valid certificate is served with no browser warnings.",
                command="curl -Iv https://opennow.io 2>&1 | grep -E 'SSL connection|expire date'",
                expected_output="SSL connection using TLSv1.3, expire date > 30 days in future."
            )
        ]

        return RunbookResponse(
            task_id=request.task_id,
            runbook_id="RB-SEC-SSL-RENEW-04",
            runbook_title="TLS/SSL Certificate Expiry & Emergency Ingress Renewal",
            category="Security",
            target_ci=request.ci_id or "ci-kong-api-gateway",
            estimated_duration="10 minutes",
            prerequisites=["openssl", "kubectl with cert-manager plugin", "DNS provider access if manual verification needed"],
            diagnostic_commands=[
                "openssl s_client -connect opennow.io:443 -servername opennow.io </dev/null",
                "kubectl get certificate,certificaterequest,order,challenge -n production"
            ],
            steps=steps,
            verification_steps=[
                "Run external synthetic SSL check via curl",
                "Verify browser SSL padlock displays valid DigiCert/Let's Encrypt certificate"
            ],
            rollback_plan=[
                "If ACME automation fails, manually upload wildcard backup certificate secret: 'kubectl create secret tls opennow-tls --cert=backup.crt --key=backup.key -n production --dry-run=client -o yaml | kubectl apply -f -'"
            ],
            safety_notes=[
                "Ensure CA root bundles are updated on origin servers to avoid intermediate certificate trust issues"
            ]
        )

    def _build_payment_gateway_runbook(self, request: RunbookRequest) -> RunbookResponse:
        steps = [
            RunbookStep(
                step_number=1,
                phase="Diagnostic",
                title="Check Stripe Gateway Status and Webhook Error Log",
                description="Inspect payment worker logs for 401 signature mismatches or API rate limits.",
                command="kubectl logs -l app=payment-service -n production --tail=100 | grep -E 'Stripe|Webhook|401|429'",
                expected_output="Inspect HTTP response codes from payment processor."
            ),
            RunbookStep(
                step_number=2,
                phase="Diagnostic",
                title="Verify Webhook Signing Secret & API Keys",
                description="Ensure payment gateway signing secrets in production Kubernetes secrets match Stripe dashboard.",
                command="kubectl get secret payment-secrets -n production -o jsonpath='{.data.STRIPE_WEBHOOK_SECRET}' | base64 -d",
                safety_warning="Handle API keys with care. Do not log decrypted values to public channels."
            ),
            RunbookStep(
                step_number=3,
                phase="Containment",
                title="Enable Asynchronous Order Hold Queue",
                description="Activate the resilient order hold queue so customer orders are accepted and queued rather than dropped.",
                command="kubectl patch configmap payment-config -n production --type merge -p '{\"data\":{\"ASYNC_HOLD_ENABLED\":\"true\"}}'",
                expected_output="ConfigMap patched."
            ),
            RunbookStep(
                step_number=4,
                phase="Remediation",
                title="Replay Failed Dead-Letter Webhooks",
                description="Trigger worker consumer to reprocess dead-letter queue (DLQ) messages with idempotency keys.",
                command="kubectl exec -it deployment/payment-service -n production -- python manage.py replay_dlq --limit=500",
                expected_output="Successfully replayed payments."
            ),
            RunbookStep(
                step_number=5,
                phase="Verification",
                title="Run Synthetic Test Transaction",
                description="Execute an end-to-end sandbox checkout test transaction to verify charge capture and webhook receipt.",
                command="curl -sSf -X POST http://payment-service/api/v1/health/synthetic-checkout | jq .",
                expected_output="Status: 'success', transaction_id generated."
            )
        ]

        return RunbookResponse(
            task_id=request.task_id,
            runbook_id="RB-PAY-GATEWAY-05",
            runbook_title="Payment Gateway Integration & Webhook Failure Recovery",
            category="Payment",
            target_ci=request.ci_id or "ci-payment-service",
            estimated_duration="15 - 30 minutes",
            prerequisites=["Stripe Dashboard Admin access", "Production payment service CLI access"],
            diagnostic_commands=[
                "curl -sSf https://status.stripe.com/api/v2/summary.json | jq .",
                "kubectl logs -l app=payment-service -n production | grep -i error | tail -20"
            ],
            steps=steps,
            verification_steps=[
                "Confirm checkout success rate returns to > 99.5%",
                "Verify zero pending webhooks in Stripe dashboard webhook retry queue"
            ],
            rollback_plan=[
                "Switch routing traffic to backup payment processor (Adyen/PayPal) via feature flag toggle"
            ],
            safety_notes=[
                "Always verify idempotency keys are enforced before replaying payment webhook events"
            ]
        )

    def _build_network_dns_runbook(self, request: RunbookRequest) -> RunbookResponse:
        steps = [
            RunbookStep(
                step_number=1,
                phase="Diagnostic",
                title="Perform Comprehensive DNS Resolution Trace",
                description="Trace domain resolution starting from root authoritative name servers.",
                command="dig +trace +all opennow.io",
                expected_output="Clean authoritative ANSWER SECTION with correct A/CNAME records."
            ),
            RunbookStep(
                step_number=2,
                phase="Diagnostic",
                title="Inspect CoreDNS Cluster In-Memory Metrics",
                description="Check Kubernetes CoreDNS pod logs and latency forwarder metrics.",
                command="kubectl logs -l k8s-app=kube-dns -n kube-system --tail=50",
                expected_output="Look for NXDOMAIN, SERVFAIL, or upstream timeout messages."
            ),
            RunbookStep(
                step_number=3,
                phase="Containment",
                title="Bypass Cached Stale Resolvers",
                description="Flush local system resolver caches and switch to Google/Cloudflare public upstream DNS (8.8.8.8, 1.1.1.1).",
                command="systemd-resolve --flush-caches",
                expected_output="Flushed DNS cache."
            ),
            RunbookStep(
                step_number=4,
                phase="Remediation",
                title="Restart CoreDNS Daemonset / Deployment",
                description="Recycle CoreDNS instances to purge corrupted in-memory cache and re-establish VPC DNS endpoints.",
                command="kubectl rollout restart deployment/coredns -n kube-system",
                expected_output="coredns deployment restarted."
            ),
            RunbookStep(
                step_number=5,
                phase="Verification",
                title="Verify DNS Lookup Latency Benchmark",
                description="Benchmark 50 consecutive lookups to confirm response time is < 5ms.",
                command="for i in {1..10}; do dig opennow.io +noall +stats | grep 'Query time'; done",
                expected_output="Query time consistently < 5 msec."
            )
        ]

        return RunbookResponse(
            task_id=request.task_id,
            runbook_id="RB-NET-DNS-06",
            runbook_title="Network Latency & CoreDNS Resolution Failure Troubleshooting",
            category="Network",
            target_ci=request.ci_id or "ci-kong-api-gateway",
            estimated_duration="10 - 15 minutes",
            prerequisites=["dig CLI", "kubectl cluster-admin access to kube-system"],
            diagnostic_commands=[
                "dig opennow.io @8.8.8.8 +short",
                "traceroute -T -p 443 opennow.io"
            ],
            steps=steps,
            verification_steps=[
                "Confirm DNS resolution succeeds from external vantage points (US, EU, APAC)",
                "Validate p99 round-trip latency returns to standard SLA"
            ],
            rollback_plan=["Revert DNS zone modifications in Route53 or Cloudflare registrar history"],
            safety_notes=["Never lower TTL below 60s during an active DDoS attack"]
        )

    def _build_generic_runbook(self, request: RunbookRequest) -> RunbookResponse:
        steps = [
            RunbookStep(
                step_number=1,
                phase="Diagnostic",
                title="Triage & Symptom Verification",
                description="Verify incident report by collecting telemetry, error rates, and active alerting rules.",
                command="curl -sSf http://localhost:8000/api/ai/health",
                expected_output="System status and diagnostic payloads."
            ),
            RunbookStep(
                step_number=2,
                phase="Diagnostic",
                title="Collect Service Telemetry & Recent Error Logs",
                description="Tail recent application log output to isolate root cause stack traces.",
                command="tail -n 100 /var/log/application.log",
                expected_output="Specific error messages or timeout traces."
            ),
            RunbookStep(
                step_number=3,
                phase="Containment",
                title="Engage Defensive Circuit Breaking",
                description="Throttle inbound non-critical traffic to shield degraded components from cascade.",
                command="echo 'Activating rate limits and circuit breaker policy'",
                safety_warning="Ensure critical auth routes remain accessible."
            ),
            RunbookStep(
                step_number=4,
                phase="Remediation",
                title="Execute Controlled Service Recovery",
                description="Perform controlled restart or rollback of impaired services following SRE standard operating procedures.",
                command="echo 'Executing graceful service reload'",
                expected_output="Service reloaded successfully."
            ),
            RunbookStep(
                step_number=5,
                phase="Verification",
                title="Verify Golden Signals (Latency, Traffic, Errors, Saturation)",
                description="Check metrics dashboard to confirm that error rates drop to baseline and latency normalizes.",
                command="echo 'Verifying telemetry golden signals'",
                expected_output="All 4 golden signals healthy."
            )
        ]

        return RunbookResponse(
            task_id=request.task_id,
            runbook_id="RB-GEN-SRE-00",
            runbook_title="Standard SRE Incident Investigation & Remediation Workflow",
            category=request.category or "Application",
            target_ci=request.ci_id or "General",
            estimated_duration="20 - 30 minutes",
            prerequisites=["Production console access", "Grafana/Datadog monitoring access"],
            diagnostic_commands=["uptime", "df -h", "free -m", "ps aux --sort=-%mem | head -10"],
            steps=steps,
            verification_steps=[
                "Confirm system error rate is < 0.1%",
                "Verify all critical synthetic user journeys pass successfully"
            ],
            rollback_plan=["Rollback deployment to last known stable commit hash"],
            safety_notes=["Follow company change control and incident communication protocols"]
        )


# ============================================================================
# 4. STAKEHOLDER COMMUNICATIONS ENGINE
# ============================================================================

class StakeholderCommunicationsEngine:
    """
    Drafts clear, executive-ready and technical incident communications across
    the four canonical incident lifecycles:
    1. Investigating (Initial notification)
    2. Identified (Root cause isolated)
    3. Mitigated (Services stabilizing)
    4. Resolved (Post-incident root cause summary)
    """

    def draft(self, request: CommunicationDraftRequest) -> CommunicationDraftResponse:
        audience = (request.audience or "stakeholder").lower()
        phase = (request.phase or "investigating").lower()
        task_id = request.task_id or "INC-UNASSIGNED"
        title = request.title or "Service Degradation Incident"
        ci_id = request.ci_id or "Production Systems"
        custom_details = request.details or ""

        if audience == "technical":
            return self._draft_technical(task_id, title, ci_id, phase, custom_details)
        else:
            return self._draft_stakeholder(task_id, title, ci_id, phase, custom_details)

    def _draft_stakeholder(
        self, task_id: str, title: str, ci_id: str, phase: str, details: str
    ) -> CommunicationDraftResponse:
        timestamp_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

        if phase == "investigating":
            subject = f"[UPDATE] Investigating Service Interruption: {title}"
            md = (
                f"### Incident Notification: Service Interruption\n\n"
                f"**Timestamp:** {timestamp_str}\n"
                f"**Status:** Under Active Investigation\n"
                f"**Reference:** `{task_id}`\n\n"
                f"**Summary:**\n"
                f"Our operations team is currently investigating an issue impacting **{title}**. "
                f"Users may experience intermittent errors, slower loading times, or difficulty accessing related features.\n\n"
                f"**Current Action:**\n"
                f"Our engineering and SRE teams have been dispatched to isolate the root cause and restore normal performance as quickly as possible.\n\n"
                f"{f'**Additional Context:** {details}' if details else ''}\n\n"
                f"**Next Update:** Within 30 minutes or immediately as significant progress is made."
            )
            channels = ["StatusPage", "Executive Email Distribution", "#all-company-announcements"]
            next_window = "30 minutes"
            approval = False

        elif phase == "identified":
            subject = f"[UPDATE] Root Cause Identified: {title}"
            md = (
                f"### Incident Update: Root Cause Isolated\n\n"
                f"**Timestamp:** {timestamp_str}\n"
                f"**Status:** Remediation In Progress\n"
                f"**Reference:** `{task_id}`\n\n"
                f"**Summary:**\n"
                f"We have identified the root cause contributing to the performance degradation in **{title}**. "
                f"The issue has been traced to a component level event in `{ci_id}`.\n\n"
                f"**Remediation Steps:**\n"
                f"Our technical leads have initiated controlled remediation procedures to restore full functionality. "
                f"We are observing early signs of stabilization.\n\n"
                f"{f'**Engineering Notes:** {details}' if details else ''}\n\n"
                f"**Next Update:** Within 30 minutes upon verification of system recovery."
            )
            channels = ["StatusPage", "Executive Email Distribution"]
            next_window = "30 minutes"
            approval = False

        elif phase == "mitigated":
            subject = f"[UPDATE] Service Restored / Monitoring: {title}"
            md = (
                f"### Incident Update: Service Restored & Under Active Monitoring\n\n"
                f"**Timestamp:** {timestamp_str}\n"
                f"**Status:** Mitigated / Monitoring\n"
                f"**Reference:** `{task_id}`\n\n"
                f"**Summary:**\n"
                f"Remediation actions deployed for **{title}** have successfully mitigated the interruption. "
                f"Customer-facing services are functioning normally and transaction success rates have returned to baseline.\n\n"
                f"**Next Steps:**\n"
                f"Our teams remain on active watch to monitor system telemetry and ensure sustained platform stability.\n\n"
                f"{f'**Details:** {details}' if details else ''}\n\n"
                f"**Next Update:** Final resolution summary will follow after the observation period concludes."
            )
            channels = ["StatusPage", "Customer Support Broadcast"]
            next_window = "45 minutes"
            approval = False

        else:  # resolved
            subject = f"[RESOLVED] Service Operational: {title}"
            md = (
                f"### Incident Resolution: {title}\n\n"
                f"**Timestamp:** {timestamp_str}\n"
                f"**Status:** Fully Resolved\n"
                f"**Reference:** `{task_id}`\n\n"
                f"**Resolution Summary:**\n"
                f"The incident impacting **{title}** has been fully resolved. All associated services are 100% operational with normal latency and zero elevated error rates.\n\n"
                f"**Preventative Measures:**\n"
                f"A comprehensive post-incident review (PIR) is underway to implement safeguards preventing recurrence. "
                f"We sincerely apologize for any inconvenience caused to your operations.\n\n"
                f"{f'**Root Cause Detail:** {details}' if details else ''}"
            )
            channels = ["StatusPage", "Executive Email Distribution", "Customer Support Portal"]
            next_window = "None - Incident Closed"
            approval = True

        plain_text = re.sub(r"[*#`]", "", md)

        return CommunicationDraftResponse(
            task_id=task_id,
            audience="stakeholder",
            phase=phase,
            subject=subject,
            body_markdown=md,
            body_plain=plain_text.strip(),
            target_channels=channels,
            next_update_window=next_window,
            approval_required=approval
        )

    def _draft_technical(
        self, task_id: str, title: str, ci_id: str, phase: str, details: str
    ) -> CommunicationDraftResponse:
        timestamp_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

        if phase == "investigating":
            subject = f"[INCIDENT SRE ALERT] {task_id} | {title} | {ci_id}"
            md = (
                f"**[SRE / DEVOPS INCIDENT NOTICE]**\n"
                f"- **Ticket:** `{task_id}`\n"
                f"- **Target Component / CI:** `{ci_id}`\n"
                f"- **Current Phase:** INVESTIGATING\n"
                f"- **Reported At:** `{timestamp_str}`\n\n"
                f"**Telemetry & Symptoms:**\n"
                f"{title}\n\n"
                f"**Immediate Actions:**\n"
                f"1. On-Call primary paged via PagerDuty\n"
                f"2. War-room bridge spun up on Slack `#inc-{task_id.lower()}`\n"
                f"3. Logs, traces, and metrics pinned on Datadog dashboard\n\n"
                f"{f'**Diagnostic Notes:** {details}' if details else ''}"
            )
            channels = [f"#inc-{task_id.lower()}", "#sre-alerts", "PagerDuty Incident Bridge"]
            next_window = "15 minutes"

        elif phase == "identified":
            subject = f"[TECHNICAL UPDATE] {task_id} Root Cause Isolated: {ci_id}"
            md = (
                f"**[SRE / DEVOPS INCIDENT UPDATE]**\n"
                f"- **Ticket:** `{task_id}`\n"
                f"- **Target Component / CI:** `{ci_id}`\n"
                f"- **Phase:** ROOT CAUSE IDENTIFIED\n\n"
                f"**Root Cause Diagnosis:**\n"
                f"{details or 'Root cause isolated to anomalous resource saturation or downstream lock contention.'}\n\n"
                f"**Active Runbook Execution:**\n"
                f"Remediation procedures in progress. Re-routing traffic and recycling affected pods/connections."
            )
            channels = [f"#inc-{task_id.lower()}", "#sre-alerts"]
            next_window = "20 minutes"

        elif phase == "mitigated":
            subject = f"[TECHNICAL UPDATE] {task_id} Mitigated - Entering Soak Period"
            md = (
                f"**[SRE / DEVOPS INCIDENT UPDATE]**\n"
                f"- **Ticket:** `{task_id}`\n"
                f"- **Phase:** MITIGATED / MONITORING\n\n"
                f"**Mitigation Executed:**\n"
                f"{details or 'Traffic restored, error rates dropped below 0.05%, p95 latency normalized.'}\n\n"
                f"**Soak Period:**\n"
                f"System will remain under active SRE observation for 30 minutes before final ticket closure."
            )
            channels = [f"#inc-{task_id.lower()}", "#sre-alerts"]
            next_window = "30 minutes"

        else:  # resolved
            subject = f"[INCIDENT RESOLVED] {task_id} Closed - Post-Mortem Scheduled"
            md = (
                f"**[SRE INCIDENT CLOSURE & POST-MORTEM]**\n"
                f"- **Ticket:** `{task_id}`\n"
                f"- **Status:** RESOLVED\n"
                f"- **Impacted CI:** `{ci_id}`\n\n"
                f"**Summary of Impact & Resolution:**\n"
                f"{title}\n\n"
                f"**Post-Mortem Action Items:**\n"
                f"1. Schedule blameless post-mortem within 48 hours\n"
                f"2. File preventive engineering Jira backlog items\n"
                f"3. Update synthetic health checks and alert thresholds\n\n"
                f"{f'**Closure Notes:** {details}' if details else ''}"
            )
            channels = [f"#inc-{task_id.lower()}", "#devops-leadership", "Incident Repository"]
            next_window = "None - Closed"

        plain = re.sub(r"[*#`]", "", md)
        return CommunicationDraftResponse(
            task_id=task_id,
            audience="technical",
            phase=phase,
            subject=subject,
            body_markdown=md,
            body_plain=plain.strip(),
            target_channels=channels,
            next_update_window=next_window,
            approval_required=False
        )


# ============================================================================
# 5. MASTER OPENNOW CO-PILOT COORDINATOR
# ============================================================================

class OpenNowCoPilot:
    """
    Unified AI Co-Pilot & Automation Engine for OpenNow.
    Exposes high-level methods for triage, blast radius, runbooks, and communications.
    """

    def __init__(
        self,
        cmdb_nodes: Optional[Dict[str, Dict[str, Any]]] = None,
        cmdb_relationships: Optional[List[Tuple[str, str, str]]] = None
    ):
        self.triage_engine = IncidentTriageEngine(cmdb_nodes=cmdb_nodes)
        self.blast_radius_engine = CMDBBlastRadiusEngine(nodes=cmdb_nodes, relationships=cmdb_relationships)
        self.runbook_synthesizer = RunbookSynthesizer()
        self.comms_engine = StakeholderCommunicationsEngine()

    def triage_ticket(self, title: str, description: str, task_id: Optional[str] = None) -> TriageResponse:
        req = TriageRequest(title=title, description=description, task_id=task_id)
        return self.triage_engine.triage(req)

    def analyze_blast_radius(self, ci_id: str, max_depth: int = 5) -> BlastRadiusResponse:
        req = BlastRadiusRequest(ci_id=ci_id, max_depth=max_depth)
        return self.blast_radius_engine.analyze_blast_radius(req)

    def generate_runbook(
        self,
        task_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        ci_id: Optional[str] = None
    ) -> RunbookResponse:
        req = RunbookRequest(
            task_id=task_id,
            title=title,
            description=description,
            category=category,
            ci_id=ci_id
        )
        return self.runbook_synthesizer.synthesize(req)

    def draft_communication(
        self,
        task_id: Optional[str] = None,
        title: Optional[str] = None,
        audience: str = "stakeholder",
        phase: str = "investigating",
        ci_id: Optional[str] = None,
        details: Optional[str] = None
    ) -> CommunicationDraftResponse:
        req = CommunicationDraftRequest(
            task_id=task_id,
            title=title,
            audience=audience,
            phase=phase,
            ci_id=ci_id,
            details=details
        )
        return self.comms_engine.draft(req)

    def list_cmdb_catalog(self) -> List[Dict[str, Any]]:
        """Returns the full catalog of known Configuration Items."""
        return list(self.blast_radius_engine.nodes.values())


# Global singleton instance
copilot = OpenNowCoPilot()
