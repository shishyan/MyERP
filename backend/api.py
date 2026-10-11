"""OpenNow Core REST API
Enterprise FastAPI REST service providing ITIL Task Management, Dynamic Schema attributes,
CMDB Topology Graph queries, Real-Time Automation triggers, and Universal Migration Engine.
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.database import db
from backend.migration_engine import migration_engine
from backend.models import (
    ActivityLog,
    ActivityLogCreate,
    CI,
    CICreate,
    CIUpdate,
    CMDBGraphResponse,
    CIRelationshipCreate,
    StatsResponse,
    Task,
    TaskCreate,
    TaskDetailResponse,
    TaskUpdate,
)

# Initialize FastAPI App
app = FastAPI(
    title="OpenNow Enterprise Backend API",
    description="Next-Generation Open-Source ITIL Service Platform & Autonomous CMDB Engine",
    version="2.4.0",
)

# CORS Middleware (Universal Access for Web Clients)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI Co-Pilot Reasoning Engine
from ai_engine.router import router as ai_router
app.include_router(ai_router)

# Master Data Configuration Engine Router
from backend.config_engine import config_router
app.include_router(config_router)

# ITIL Incident Management V2 Router
from backend.incident_api import router as incident_router
app.include_router(incident_router)

# Full Enterprise ITSM Suite Router (Problems, Changes, Releases, Catalog, Requests, KCS, ITAM)
from backend.full_itsm_engine import itsm_router
app.include_router(itsm_router)

# Omnichannel Telecom & Email Engine Router (Mail-to-Ticket, Smart Threading, CTI Screen Pop, PBX Webhooks)
from backend.omnichannel_engine import omnichannel_router
app.include_router(omnichannel_router)


# --- Startup & Health ---

@app.on_event("startup")
def on_startup() -> None:
    """Ensure database schema is ready and pre-seeded if empty."""
    tasks = db.list_tasks(limit=1)
    if not tasks:
        db.seed_data()


@app.get("/api/health", tags=["System"])
def get_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "OpenNow Enterprise Backend",
        "version": "2.4.0",
        "storage": "SQLite-WAL",
        "dynamic_schema": True,
    }


@app.post("/api/seed", tags=["System"])
def seed_database() -> Dict[str, Any]:
    """Resets database and populates high-fidelity HA microservices architecture and enterprise tickets."""
    db.seed_data()
    metrics = db.get_metrics_and_stats()
    return {
        "success": True,
        "message": "Database successfully populated with enterprise seed datasets.",
        "metrics": metrics,
    }


# --- Task / Incident / Change / Problem / Request Endpoints ---

@app.get("/api/tasks", response_model=List[Task], tags=["Tasks"])
def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status (new, in_progress, on_hold, resolved, closed)"),
    priority: Optional[str] = Query(None, description="Filter by priority (P1, P2, P3, P4)"),
    task_type: Optional[str] = Query(None, alias="type", description="Filter by task_type (incident, change, problem, request)"),
    search: Optional[str] = Query(None, description="Full-text query across title, description, task_number, caller"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[Dict[str, Any]]:
    """Lists enterprise tasks with multi-facet filtering and full-text search."""
    return db.list_tasks(
        status=status,
        priority=priority,
        task_type=task_type,
        search=search,
        limit=limit,
        offset=offset,
    )


@app.post("/api/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
def create_task(payload: TaskCreate) -> Dict[str, Any]:
    """Creates a task with auto-generated INC/CHG numbers, executes automation triggers, and sets SLA."""
    task_dict = payload.model_dump(exclude={"affected_ci_ids"})
    affected_cis = payload.affected_ci_ids or []
    created = db.create_task(task_dict, affected_ci_ids=affected_cis)
    return created


@app.get("/api/tasks/{task_id}", response_model=TaskDetailResponse, tags=["Tasks"])
def get_task_detail(task_id: int) -> Dict[str, Any]:
    """Retrieves full task details including immutable activity audit trail and affected CIs."""
    detail = db.get_task_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found.")
    return detail


@app.patch("/api/tasks/{task_id}", response_model=Task, tags=["Tasks"])
def update_task(task_id: int, payload: TaskUpdate, author: str = Query("Engineer", description="Author of changes")) -> Dict[str, Any]:
    """Updates task attributes, recalculates SLAs, evaluates automation rules, and logs transitions."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        existing = db.get_task_by_id(task_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found")
        return existing

    updated = db.update_task(task_id, updates, author=author)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found.")
    return updated


@app.post("/api/tasks/{task_id}/activities", response_model=ActivityLog, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
def add_task_activity(task_id: int, payload: ActivityLogCreate) -> Dict[str, Any]:
    """Appends a comment, status transition audit, or AI triage analysis to a task."""
    task = db.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found.")

    return db.add_activity(
        task_id=task_id,
        author=payload.author,
        message=payload.message,
        activity_type=payload.activity_type.value if hasattr(payload.activity_type, "value") else str(payload.activity_type),
    )


# --- CMDB / Configuration Item Endpoints ---

@app.get("/api/cmdb/cis", response_model=List[CI], tags=["CMDB"])
def list_configuration_items(
    ci_type: Optional[str] = Query(None, description="Filter by CI type"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    health_status: Optional[str] = Query(None, description="Filter by health status"),
) -> List[Dict[str, Any]]:
    """Lists configuration items with filtering."""
    return db.list_cis(
        ci_type=ci_type,
        environment=environment,
        health_status=health_status,
    )


@app.post("/api/cmdb/cis", response_model=CI, tags=["CMDB"])
def create_or_update_ci(payload: CICreate) -> Dict[str, Any]:
    """Creates or updates a Configuration Item (CI) with dynamic JSON metadata."""
    ci_dict = payload.model_dump()
    return db.create_or_update_ci(ci_dict)


@app.get("/api/cmdb/cis/{ci_id}", tags=["CMDB"])
def get_ci_detail(ci_id: int) -> Dict[str, Any]:
    """Retrieves CI details, related incident tasks, and dependency graph connections."""
    ci = db.get_ci_by_id(ci_id)
    if not ci:
        raise HTTPException(status_code=404, detail=f"CI with ID {ci_id} not found.")

    # Find tasks affecting this CI
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.* FROM tasks t
            JOIN task_cis tc ON t.id = tc.task_id
            WHERE tc.ci_id = ?
            ORDER BY t.id DESC
            """,
            (ci_id,),
        )
        tasks = [db._row_to_task(r) for r in cursor.fetchall()]

        # Upstream dependencies (this CI depends on)
        cursor.execute(
            """
            SELECT c.*, cr.relationship_type FROM cis c
            JOIN ci_relationships cr ON c.id = cr.target_ci_id
            WHERE cr.source_ci_id = ?
            """,
            (ci_id,),
        )
        downstream = [dict(r) for r in cursor.fetchall()]

        # Downstream dependencies (other CIs depending on this CI)
        cursor.execute(
            """
            SELECT c.*, cr.relationship_type FROM cis c
            JOIN ci_relationships cr ON c.id = cr.source_ci_id
            WHERE cr.target_ci_id = ?
            """,
            (ci_id,),
        )
        upstream = [dict(r) for r in cursor.fetchall()]

    return {
        "ci": ci,
        "affected_tasks": tasks,
        "dependencies": downstream,
        "dependents": upstream,
    }


@app.get("/api/cmdb/graph", response_model=CMDBGraphResponse, tags=["CMDB"])
def get_cmdb_graph() -> Dict[str, Any]:
    """Returns nodes and edges formatted for topological graph visualizers."""
    return db.get_cmdb_graph()


@app.post("/api/cmdb/relationships", tags=["CMDB"])
def create_ci_relationship(payload: CIRelationshipCreate) -> Dict[str, Any]:
    """Creates a directed relationship between two CIs (depends_on, runs_on, connects_to, hosted_in)."""
    return db.add_ci_relationship(
        source_ci_id=payload.source_ci_id,
        target_ci_id=payload.target_ci_id,
        relationship_type=payload.relationship_type.value,
    )


# --- Executive Stats & Operational KPIs ---

@app.get("/api/stats", response_model=StatsResponse, tags=["Analytics"])
def get_operational_stats() -> Dict[str, Any]:
    """Calculates operational KPIs: total open, P1 critical outages, MTTR hours, and SLA compliance rate."""
    return db.get_metrics_and_stats()


# --- Universal Migration Engine Endpoints ---

class MigrationAnalyzePayload(BaseModel):
    file_content: Optional[str] = Field(None, description="Raw CSV, JSON, or TSV string")
    file_name: Optional[str] = Field("export.csv", description="Original file name")
    format: Optional[str] = Field(None, description="Optional format hint (csv, json, xml)")


class MigrationExecutePayload(BaseModel):
    file_content: str = Field(..., description="Raw exported file content")
    file_name: Optional[str] = Field("export.csv", description="Original file name")
    custom_mappings: Optional[Dict[str, str]] = Field(None, description="Optional field overrides")


@app.post("/api/migration/analyze", tags=["Migration"])
async def migration_analyze(
    request: Request,
    file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Analyzes a legacy ITSM export (multipart file or JSON payload) and generates AI migration strategy."""
    file_content = ""
    file_name = "export.csv"
    format_hint = None

    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        if not file:
            form = await request.form()
            file_upload = form.get("file")
            if file_upload and hasattr(file_upload, "read"):
                content_bytes = await file_upload.read()
                file_content = content_bytes.decode("utf-8", errors="replace")
                file_name = getattr(file_upload, "filename", "export.csv")
            elif "file_content" in form:
                file_content = str(form["file_content"])
                file_name = str(form.get("file_name", "export.csv"))
        else:
            content_bytes = await file.read()
            file_content = content_bytes.decode("utf-8", errors="replace")
            file_name = file.filename or "export.csv"
    else:
        # JSON body
        try:
            body = await request.json()
            file_content = body.get("file_content", "")
            file_name = body.get("file_name", "export.csv")
            format_hint = body.get("format")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body or multipart payload.")

    if not file_content.strip():
        raise HTTPException(status_code=400, detail="No file content provided for analysis.")

    plan = migration_engine.analyze_and_plan(file_content, file_name, format_hint=format_hint)
    return plan


@app.post("/api/migration/execute", tags=["Migration"])
def migration_execute(payload: MigrationExecutePayload) -> Dict[str, Any]:
    """Executes atomic ingestion of legacy records into OpenNow database with dynamic custom field mapping."""
    result = migration_engine.execute_migration(
        file_content=payload.file_content,
        file_name=payload.file_name or "export.csv",
        custom_mappings=payload.custom_mappings,
    )
    return result


@app.post("/api/migration/top10/execute", tags=["Migration"])
def migration_top10_execute(payload: MigrationExecutePayload) -> Dict[str, Any]:
    """Executes 5-pass native relational migration for any of the Top 10 ITSM platforms."""
    from backend.top10_migrators import Top10MigrationEngine, relational_db
    engine = Top10MigrationEngine(db=relational_db)
    result = engine.execute_migration(payload.file_content)
    return result


@app.get("/api/migration/samples/{sample_id}", tags=["Migration"])
def get_migration_sample(sample_id: str) -> Dict[str, Any]:
    """Returns bundled realistic sample datasets for instant 1-click migration demo (servicenow, jira, glpi)."""
    return migration_engine.get_sample_data(sample_id)


@app.get("/api/migration/top10/samples/{platform_id}", tags=["Migration"])
def get_top10_migration_sample(platform_id: str) -> Dict[str, Any]:
    """Returns bundled authentic multi-table enterprise exports for all Top 10 platforms."""
    from backend.top10_migrators import get_sample_export, AUTHENTIC_SAMPLES
    norm_id = platform_id.lower().replace("-", "_")
    if norm_id not in AUTHENTIC_SAMPLES:
        for k in AUTHENTIC_SAMPLES.keys():
            if norm_id in k or k in norm_id:
                norm_id = k
                break
    sample_content = get_sample_export(norm_id)
    if isinstance(sample_content, (dict, list)):
        sample_str = json.dumps(sample_content, indent=2)
    else:
        sample_str = str(sample_content)
    return {
        "platform": norm_id,
        "file_name": f"{norm_id}_enterprise_export.json",
        "file_content": sample_str,
    }



# --- Static Files / Single Page Web Application ---

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
