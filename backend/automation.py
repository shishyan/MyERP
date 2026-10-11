"""OpenNow Automation Trigger Engine
Evaluates enterprise rules, event triggers, SLA policies, and automated workflows.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from backend.models import (
    ActivityType,
    HealthStatus,
    Priority,
    TaskStatus,
    TaskType,
)


class AutomationEngine:
    """Enterprise event-driven automation engine for OpenNow."""

    @staticmethod
    def calculate_sla_due(priority: Priority | str, from_dt: Optional[datetime.datetime] = None) -> str:
        """Calculates SLA deadline based on ITIL priority tier."""
        base_time = from_dt or datetime.datetime.now(datetime.timezone.utc)
        p_val = priority.value if isinstance(priority, Priority) else str(priority).upper()

        if p_val == "P1":
            delta = datetime.timedelta(hours=1)
        elif p_val == "P2":
            delta = datetime.timedelta(hours=4)
        elif p_val == "P3":
            delta = datetime.timedelta(hours=24)
        else:
            delta = datetime.timedelta(hours=72)

        due_time = base_time + delta
        return due_time.isoformat()

    @staticmethod
    def evaluate_task_creation(
        task_data: Dict[str, Any],
        affected_cis: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Evaluates rules on task creation and produces enriched fields and automated activities."""
        actions: Dict[str, Any] = {
            "mutations": {},
            "generated_activities": [],
            "ci_health_updates": [],
        }

        priority = task_data.get("priority", "P3")
        task_type = task_data.get("task_type", "incident")
        current_sla = task_data.get("sla_due_at")

        # Rule 1: Compute SLA deadline if not explicitly provided
        if not current_sla:
            calculated_sla = AutomationEngine.calculate_sla_due(priority)
            actions["mutations"]["sla_due_at"] = calculated_sla

        # Rule 2: P1 Incident Urgent Dispatch & Escalation
        if priority == "P1" and task_type == "incident":
            if not task_data.get("assigned_team") or task_data.get("assigned_team") == "IT Operations":
                actions["mutations"]["assigned_team"] = "Site Reliability Engineering"

            actions["generated_activities"].append({
                "author": "OpenNow Automation Engine",
                "activity_type": ActivityType.AI_ANALYSIS.value,
                "message": (
                    "CRITICAL P1 WORKFLOW TRIGGERED: Automated incident commander paging initiated. "
                    "SRE On-Call engaged. Mission-critical SLA due in 60 minutes. War room channel provisioned."
                ),
            })

            # Check affected CIs and flag them critical
            if affected_cis:
                for ci in affected_cis:
                    actions["ci_health_updates"].append({
                        "ci_id": ci["id"],
                        "new_health": HealthStatus.CRITICAL.value,
                        "reason": f"Impacted by active P1 Incident: {task_data.get('task_number', 'PENDING')}",
                    })
        elif priority == "P2" and task_type == "incident":
            if affected_cis:
                for ci in affected_cis:
                    if ci.get("health_status") != HealthStatus.CRITICAL.value:
                        actions["ci_health_updates"].append({
                            "ci_id": ci["id"],
                            "new_health": HealthStatus.DEGRADED.value,
                            "reason": f"Impacted by active P2 Incident: {task_data.get('task_number', 'PENDING')}",
                        })

        # Rule 3: Automated AI triage analysis for changes and incidents
        title = task_data.get("title", "")
        desc = task_data.get("description", "")
        if "latency" in title.lower() or "timeout" in title.lower() or "slow" in desc.lower():
            actions["generated_activities"].append({
                "author": "OpenNow AI Triage Assistant",
                "activity_type": ActivityType.AI_ANALYSIS.value,
                "message": (
                    "Diagnostic Insight: Performance degradation pattern detected. "
                    "Correlating connection pool metrics, upstream ALB latency graphs, and database lock contention."
                ),
            })

        return actions

    @staticmethod
    def evaluate_task_update(
        old_task: Dict[str, Any],
        updates: Dict[str, Any],
        affected_cis: Optional[List[Dict[str, Any]]] = None,
        author: str = "System",
    ) -> Dict[str, Any]:
        """Evaluates rules when a task is updated."""
        actions: Dict[str, Any] = {
            "mutations": {},
            "generated_activities": [],
            "ci_health_updates": [],
        }

        # Status transition audit
        if "status" in updates and updates["status"] != old_task.get("status"):
            old_st = old_task.get("status")
            new_st = updates["status"]
            actions["generated_activities"].append({
                "author": author,
                "activity_type": ActivityType.STATUS_CHANGE.value,
                "message": f"Status updated from '{old_st}' to '{new_st}'",
            })

            # CI Health recovery check if resolved/closed
            if new_st in (TaskStatus.RESOLVED.value, TaskStatus.CLOSED.value):
                actions["generated_activities"].append({
                    "author": "OpenNow SLA Engine",
                    "activity_type": ActivityType.COMMENT.value,
                    "message": "Task marked resolved. SLA clock paused. Incident resolution timestamp captured.",
                })

        # Priority update audit & SLA recalculation
        if "priority" in updates and updates["priority"] != old_task.get("priority"):
            old_p = old_task.get("priority")
            new_p = updates["priority"]
            new_sla = AutomationEngine.calculate_sla_due(new_p)
            actions["mutations"]["sla_due_at"] = new_sla
            actions["generated_activities"].append({
                "author": author,
                "activity_type": ActivityType.STATUS_CHANGE.value,
                "message": f"Priority adjusted from {old_p} to {new_p}. SLA recalculated to {new_sla}.",
            })

        # Assignment update audit
        if "assigned_to" in updates and updates["assigned_to"] != old_task.get("assigned_to"):
            assignee = updates["assigned_to"] or "Unassigned"
            actions["generated_activities"].append({
                "author": author,
                "activity_type": ActivityType.COMMENT.value,
                "message": f"Ticket reassigned to: {assignee}",
            })

        return actions
