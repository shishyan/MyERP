"""OpenNow Core Data Models
Enterprise-grade ITSM and CMDB domain models, schemas, and enums.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# --- Enums ---

class TaskType(str, Enum):
    INCIDENT = "incident"
    CHANGE = "change"
    PROBLEM = "problem"
    REQUEST = "request"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class TaskStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CIType(str, Enum):
    SERVER = "server"
    DATABASE = "database"
    MICROSERVICE = "microservice"
    LOAD_BALANCER = "load_balancer"
    CLOUD_SERVICE = "cloud_service"
    STORAGE = "storage"


class Environment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEV = "dev"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    RUNS_ON = "runs_on"
    CONNECTS_TO = "connects_to"
    HOSTED_IN = "hosted_in"


class ActivityType(str, Enum):
    COMMENT = "comment"
    STATUS_CHANGE = "status_change"
    AI_ANALYSIS = "ai_analysis"


# --- Task Models ---

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Short summary of the task")
    description: Optional[str] = Field("", description="Detailed task description")
    task_type: TaskType = Field(default=TaskType.INCIDENT, description="ITSM category")
    priority: Priority = Field(default=Priority.P3, description="Severity priority level")
    status: TaskStatus = Field(default=TaskStatus.NEW, description="Lifecycle status")
    caller: Optional[str] = Field("System", description="Initiator or requester username/email")
    assigned_to: Optional[str] = Field(None, description="Assigned engineer username/email")
    assigned_team: Optional[str] = Field("IT Operations", description="Assigned engineering or operations team")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Dynamic arbitrary schema-free fields")


class TaskCreate(TaskBase):
    task_number: Optional[str] = Field(None, description="Optional override, otherwise auto-generated")
    affected_ci_ids: Optional[List[int]] = Field(default_factory=list, description="IDs of affected CIs")


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[TaskType] = None
    priority: Optional[Priority] = None
    status: Optional[TaskStatus] = None
    caller: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_team: Optional[str] = None
    sla_due_at: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None
    affected_ci_ids: Optional[List[int]] = None


class Task(TaskBase):
    id: int
    task_number: str
    created_at: str
    updated_at: str
    sla_due_at: Optional[str] = None

    class Config:
        from_attributes = True


# --- Activity Log Models ---

class ActivityLogBase(BaseModel):
    author: str = Field("System", description="Author of the activity")
    message: str = Field(..., min_length=1, description="Log message or comment")
    activity_type: ActivityType = Field(default=ActivityType.COMMENT, description="Type of activity")


class ActivityLogCreate(ActivityLogBase):
    task_id: Optional[int] = None


class ActivityLog(ActivityLogBase):
    id: int
    task_id: int
    created_at: str

    class Config:
        from_attributes = True


# --- CMDB / Configuration Item Models ---

class CIBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Unique CI name")
    ci_type: CIType = Field(..., description="Configuration Item type")
    environment: Environment = Field(default=Environment.PRODUCTION, description="Deployment environment")
    ip_address: Optional[str] = Field(None, description="IPv4/IPv6 or hostname/endpoint")
    owner_team: Optional[str] = Field("Infrastructure Team", description="Responsible team")
    health_status: HealthStatus = Field(default=HealthStatus.HEALTHY, description="Current health status")
    tier: int = Field(default=2, ge=1, le=3, description="Tier criticality: 1 (Mission-Critical) to 3")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Dynamic CMDB metadata properties")


class CICreate(CIBase):
    id: Optional[int] = None


class CIUpdate(BaseModel):
    name: Optional[str] = None
    ci_type: Optional[CIType] = None
    environment: Optional[Environment] = None
    ip_address: Optional[str] = None
    owner_team: Optional[str] = None
    health_status: Optional[HealthStatus] = None
    tier: Optional[int] = Field(None, ge=1, le=3)
    metadata: Optional[Dict[str, Any]] = None


class CI(CIBase):
    id: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# --- CMDB Relationship Models ---

class CIRelationshipBase(BaseModel):
    source_ci_id: int = Field(..., description="ID of source CI")
    target_ci_id: int = Field(..., description="ID of target CI")
    relationship_type: RelationshipType = Field(..., description="Nature of relationship")


class CIRelationshipCreate(CIRelationshipBase):
    pass


class CIRelationship(CIRelationshipBase):
    id: int
    created_at: str

    class Config:
        from_attributes = True


# --- Combined & Graph Models ---

class TaskDetailResponse(BaseModel):
    task: Task
    activity_logs: List[ActivityLog] = Field(default_factory=list)
    affected_cis: List[CI] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: int
    name: str
    ci_type: str
    environment: str
    health_status: str
    tier: int
    ip_address: Optional[str] = None
    owner_team: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: int
    source: int
    target: int
    relationship_type: str


class CMDBGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class StatsResponse(BaseModel):
    total_tasks: int
    total_open: int
    p1_critical_count: int
    mttr_hours: float
    sla_compliance_rate: float
    by_status: Dict[str, int]
    by_priority: Dict[str, int]
    by_type: Dict[str, int]
    ci_health_breakdown: Dict[str, int]
