"""
OpenNow AI Co-Pilot FastAPI Router
==================================
Exposes the AI Co-Pilot REST API endpoints for:
- POST /api/ai/triage
- POST /api/ai/blast-radius
- POST /api/ai/generate-runbook
- POST /api/ai/draft-communication
- GET  /api/ai/cmdb/catalog
- GET  /api/ai/health
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ai_engine.copilot import (
    copilot,
    TriageRequest,
    TriageResponse,
    BlastRadiusRequest,
    BlastRadiusResponse,
    RunbookRequest,
    RunbookResponse,
    CommunicationDraftRequest,
    CommunicationDraftResponse,
)

router = APIRouter(prefix="/api/ai", tags=["AI Co-Pilot"])

# In-memory ticket / incident cache for easy resolution by task_id
INCIDENT_STORE: Dict[str, Dict[str, Any]] = {
    "INC-1001": {
        "task_id": "INC-1001",
        "title": "PostgreSQL Aurora Primary connection pool exhausted and deadlock cascade",
        "description": "API Gateway returning 500 across all checkout routes. Database CPU at 99%, active connections at 1000/1000 limit.",
        "category": "Database",
        "priority": "P1",
        "ci_id": "ci-db-postgres-primary"
    },
    "INC-1002": {
        "task_id": "INC-1002",
        "title": "Kubernetes Pod CrashLoopBackOff after deployment on ingress controller",
        "description": "Kong Ingress pods are crashing immediately upon start. Exit code 1 with invalid configuration in ConfigMap.",
        "category": "Infrastructure",
        "priority": "P1",
        "ci_id": "ci-kong-api-gateway"
    },
    "INC-1003": {
        "task_id": "INC-1003",
        "title": "Memory leak in Auth service causing OOMKilled every 45 minutes",
        "description": "User Auth pod RSS memory climbs steadily from 400MB to 4GB before cgroup OOM killer terminates it.",
        "category": "Infrastructure",
        "priority": "P2",
        "ci_id": "ci-auth-service"
    },
    "INC-1004": {
        "task_id": "INC-1004",
        "title": "SSL/TLS handshake failure on opennow.io domain",
        "description": "Browsers warning certificate has expired. cert-manager ACME challenge failed with DNS timeout.",
        "category": "Security",
        "priority": "P1",
        "ci_id": "ci-kong-api-gateway"
    },
    "INC-1005": {
        "task_id": "INC-1005",
        "title": "Stripe webhook 401 signature verification failures blocking order payments",
        "description": "Stripe webhook events failing verification after rotating secret key in Vault. Customers unable to finalize carts.",
        "category": "Payment",
        "priority": "P1",
        "ci_id": "ci-payment-service"
    },
    "INC-1006": {
        "task_id": "INC-1006",
        "title": "Internal developer unable to access sandbox Okta group",
        "description": "Single engineer cannot log in to staging test bench. Okta group membership missing.",
        "category": "Access",
        "priority": "P4",
        "ci_id": "ci-admin-portal"
    },
    "INC-9042": {
        "task_id": "INC-9042",
        "title": "Database connection pool exhausted on primary RDS",
        "description": "PostgreSQL Aurora Primary connection pool reaches max_connections limit. Multiple active queries blocked.",
        "category": "Database",
        "priority": "P1",
        "ci_id": "ci-db-postgres-primary"
    },
    "INC-9043": {
        "task_id": "INC-9043",
        "title": "Checkout failure spikes on Payment Gateway",
        "description": "Stripe webhook 504 gateway timeout surge. Customer payment capture failing across web and mobile clients.",
        "category": "Payment",
        "priority": "P1",
        "ci_id": "ci-payment-service"
    },
    "INC-9044": {
        "task_id": "INC-9044",
        "title": "Redis cache high memory eviction and latency surge",
        "description": "Redis memory eviction spike during high volume traffic. Session lookups degraded.",
        "category": "Infrastructure",
        "priority": "P2",
        "ci_id": "ci-redis-cache"
    },
    "INC-9045": {
        "task_id": "INC-9045",
        "title": "Kong API Gateway 502 Bad Gateway error surge",
        "description": "Ingress reverse proxy pods experiencing upstream connect failures. Intermittent 502 errors.",
        "category": "Network",
        "priority": "P1",
        "ci_id": "ci-kong-api-gateway"
    },
    "INC-9046": {
        "task_id": "INC-9046",
        "title": "Auth0 and JWT token issuance latency degradation",
        "description": "User authentication requests taking > 2000ms. Token verification queues backing up.",
        "category": "Access",
        "priority": "P2",
        "ci_id": "ci-auth-service"
    },
    "INC-9048": {
        "task_id": "INC-9048",
        "title": "Kafka order event bus partition replication lag",
        "description": "Consumer group lag exceeding 50,000 messages on topic orders.checkout.events.",
        "category": "Infrastructure",
        "priority": "P2",
        "ci_id": "ci-analytics-pipeline"
    },
    "INC-9049": {
        "task_id": "INC-9049",
        "title": "Cloudflare edge TLS certificate renewal failure",
        "description": "Edge TLS handshake failing intermittently due to expired wildcard certificate challenge.",
        "category": "Security",
        "priority": "P1",
        "ci_id": "ci-kong-api-gateway"
    }
}


@router.get("/health")
def get_health() -> Dict[str, Any]:
    """Health check for AI Co-Pilot engine and CMDB graph status."""
    return {
        "status": "healthy",
        "engine": "OpenNow AI Co-Pilot Reasoning Engine v1.0",
        "cmdb_nodes_loaded": len(copilot.blast_radius_engine.nodes),
        "cmdb_relationships_loaded": len(copilot.blast_radius_engine.relationships),
        "cached_incidents": len(INCIDENT_STORE)
    }


@router.post("/triage", response_model=TriageResponse)
def triage_incident(request: TriageRequest) -> TriageResponse:
    """
    Intelligently triage raw incident title and description:
    - Calculates recommended priority (P1-P4)
    - Detects Category (Security, Database, Payment, Infrastructure, Network, Access, Application)
    - Recommends Assignment Team
    - Computes Sentiment & Urgency score (0.0 to 1.0)
    - Identifies mentioned CIs in text
    - Evaluates automated escalation rules & SLA targets
    """
    if not request.title:
        raise HTTPException(status_code=400, detail="Incident title is required for triage analysis.")
    
    response = copilot.triage_engine.triage(request)
    
    # If task_id provided, store or update in in-memory store
    if request.task_id:
        INCIDENT_STORE[request.task_id] = {
            "task_id": request.task_id,
            "title": request.title,
            "description": request.description,
            "category": response.category,
            "priority": response.priority_code,
            "ci_id": response.identified_cis[0]["ci_id"] if response.identified_cis else None
        }
    
    return response


def resolve_task_data(task_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not task_id:
        return None
    if task_id in INCIDENT_STORE:
        return INCIDENT_STORE[task_id]
    try:
        from backend.database import db
        task = db.get_task_by_number(task_id)
        if not task and task_id.isdigit():
            task = db.get_task_by_id(int(task_id))
        if task:
            cis = db.get_affected_cis_for_task(task["id"])
            primary_ci = cis[0]["name"] if cis else None
            return {
                "task_id": task["task_number"],
                "title": task["title"],
                "description": task["description"],
                "category": task.get("task_type", "incident").capitalize(),
                "priority": task["priority"],
                "ci_id": primary_ci
            }
    except Exception:
        pass
    return None


@router.post("/blast-radius", response_model=BlastRadiusResponse)
def compute_blast_radius(request: BlastRadiusRequest) -> BlastRadiusResponse:
    """
    Traverse CMDB dependency graph starting from target CI ID:
    - Calculates upstream dependencies (what this service relies on)
    - Calculates downstream blast radius (what will break if this CI fails)
    - Computes composite risk score (0-100) and risk level (CRITICAL, HIGH, MEDIUM, LOW)
    - Identifies critical customer/business operations impacted
    - Generates actionable containment actions
    """
    if not request.ci_id:
        raise HTTPException(status_code=400, detail="ci_id is required.")
    
    return copilot.blast_radius_engine.analyze_blast_radius(request)


@router.post("/generate-runbook", response_model=RunbookResponse)
def generate_runbook(request: RunbookRequest) -> RunbookResponse:
    """
    Synthesize an actionable diagnostic and remediation runbook:
    - If task_id is provided, looks up incident context from repository
    - Tailors exact CLI commands, verification steps, and rollback plans
    """
    # If task_id provided and fields missing, enrich from cache or database
    if request.task_id:
        cached = resolve_task_data(request.task_id)
        if cached:
            if not request.title:
                request.title = cached.get("title")
            if not request.description:
                request.description = cached.get("description")
            if not request.category:
                request.category = cached.get("category")
            if not request.ci_id:
                request.ci_id = cached.get("ci_id")

    if not request.title and not request.category and not request.description:
        raise HTTPException(
            status_code=400,
            detail="Must provide either a recognized task_id or title/description/category to synthesize a runbook."
        )

    return copilot.runbook_synthesizer.synthesize(request)


@router.post("/draft-communication", response_model=CommunicationDraftResponse)
def draft_communication(request: CommunicationDraftRequest) -> CommunicationDraftResponse:
    """
    Draft customer or executive-ready incident updates:
    - Audience: 'stakeholder' (clear, non-technical, empathetic) or 'technical' (SRE/DevOps alert)
    - Phase: 'investigating', 'identified', 'mitigated', or 'resolved'
    """
    # If task_id provided and fields missing, enrich from cache or database
    if request.task_id:
        cached = resolve_task_data(request.task_id)
        if cached:
            if not request.title:
                request.title = cached.get("title")
            if not request.ci_id:
                request.ci_id = cached.get("ci_id")

    return copilot.comms_engine.draft(request)


@router.get("/cmdb/catalog")
def get_cmdb_catalog() -> Dict[str, Any]:
    """Retrieve full catalog of registered Configuration Items and relationships."""
    return {
        "nodes": list(copilot.blast_radius_engine.nodes.values()),
        "relationships": [
            {"source": s, "target": t, "type": r}
            for s, t, r in copilot.blast_radius_engine.relationships
        ]
    }
