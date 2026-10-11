"""OpenNow Incident Management V2 REST API Test Suite
======================================================
Tests all ITIL Incident endpoints, taxonomy tree, auto-priority matrix,
SLA clock pause/resume, technician worklogs, labor cost calculation,
subtasks, executive KPIs, and strict lifecycle state transition guards.
"""

import os
import sys
import unittest

# Ensure OpenNow root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.api import app


class TestIncidentManagementAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_taxonomy_tree(self):
        """Verify GET /api/v2/incidents/taxonomy/tree returns 3-tier category hierarchy."""
        response = self.client.get("/api/v2/incidents/taxonomy/tree")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("categories", data)
        self.assertIn("taxonomy", data)
        self.assertIn("category_names", data)
        self.assertIn("Hardware", data["category_names"])
        self.assertIn("Software", data["category_names"])
        self.assertIn("Database", data["category_names"])
        self.assertIn("Security", data["category_names"])
        self.assertIn("Cloud & Infrastructure", data["category_names"])

        # Verify 3-tier structure: Category -> Subcategory -> Items
        db_cat = next(c for c in data["categories"] if c["name"] == "Database")
        self.assertGreater(len(db_cat["subcategories"]), 0)
        first_sub = db_cat["subcategories"][0]
        self.assertIn("name", first_sub)
        self.assertIn("items", first_sub)
        self.assertGreater(len(first_sub["items"]), 0)

    def test_02_priority_matrix_calculate(self):
        """Verify POST /api/v2/incidents/priority-matrix/calculate returns correct ITIL priority."""
        # High + High -> P1
        r1 = self.client.post("/api/v2/incidents/priority-matrix/calculate", json={"impact": "1 - High", "urgency": "1 - High"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["priority"], "P1")
        self.assertEqual(r1.json()["sla_target_hours"], 1.0)

        # High + Medium -> P2
        r2 = self.client.post("/api/v2/incidents/priority-matrix/calculate", json={"impact": "1 - High", "urgency": "2 - Medium"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["priority"], "P2")
        self.assertEqual(r2.json()["sla_target_hours"], 4.0)

        # Medium + Medium -> P3
        r3 = self.client.post("/api/v2/incidents/priority-matrix/calculate", json={"impact": "2", "urgency": "2"})
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.json()["priority"], "P3")
        self.assertEqual(r3.json()["sla_target_hours"], 8.0)

        # Low + Low -> P4
        r4 = self.client.post("/api/v2/incidents/priority-matrix/calculate", json={"impact": "3 - Low", "urgency": "3 - Low"})
        self.assertEqual(r4.status_code, 200)
        self.assertEqual(r4.json()["priority"], "P4")
        self.assertEqual(r4.json()["sla_target_hours"], 24.0)

    def test_03_get_kpis(self):
        """Verify GET /api/v2/incidents/stats/kpi returns executive KPIs."""
        response = self.client.get("/api/v2/incidents/stats/kpi")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("fcr_rate", data)
        self.assertIn("mttr_hours", data)
        self.assertIn("mttr_minutes", data)
        self.assertIn("active_sla_breaches", data)
        self.assertIn("total_labor_cost", data)
        self.assertIn("total_incidents", data)
        self.assertGreater(data["total_incidents"], 0)

    def test_04_create_incident_auto_priority_and_business_rules(self):
        """Verify POST /api/v2/incidents evaluates priority matrix and automated business rules."""
        # 1. P1 auto-matrix calculation and Major Incident Response Team routing
        payload_p1 = {
            "title": "Core Checkout Gateway Outage",
            "description": "Payment authorization cluster failing 100% of requests.",
            "category": "Software",
            "subcategory": "Custom Services",
            "item": "Payment Processing Exception",
            "impact": "1 - High",
            "urgency": "1 - High",
            "caller": "ops-monitor@opennow.io"
        }
        resp1 = self.client.post("/api/v2/incidents", json=payload_p1)
        self.assertEqual(resp1.status_code, 201)
        inc1 = resp1.json()
        self.assertEqual(inc1["priority"], "P1")
        self.assertEqual(inc1["assignment_group"], "Major Incident Response Team")
        self.assertEqual(inc1["sla_target_hours"], 1.0)
        self.assertIn("AUTO_PRIORITY_MATRIX_P1", inc1.get("business_rules_applied", []))
        self.assertIn("P1_AUTO_MAJOR_INCIDENT_TEAM", inc1.get("business_rules_applied", []))

        # 2. Security Incident auto-routing to SOC
        payload_sec = {
            "title": "Phishing campaign with suspicious payload detected",
            "description": "Multiple employees received credential harvester.",
            "category": "Security",
            "subcategory": "Threats & Incidents",
            "item": "Phishing Campaign Influx",
            "impact": "2 - Medium",
            "urgency": "2 - Medium",
            "caller": "user@opennow.io"
        }
        resp2 = self.client.post("/api/v2/incidents", json=payload_sec)
        self.assertEqual(resp2.status_code, 201)
        inc2 = resp2.json()
        self.assertEqual(inc2["assignment_group"], "Cybersecurity SOC")
        self.assertIn("SECURITY_ROUTED_TO_SOC", inc2.get("business_rules_applied", []))

        # 3. VIP Caller Escalation
        payload_vip = {
            "title": "Executive laptop docking station failure",
            "description": "Dual monitors not displaying for VP.",
            "category": "Hardware",
            "subcategory": "Workstation",
            "item": "Docking Station",
            "impact": "3 - Low",
            "urgency": "3 - Low",
            "caller": "ceo@opennow.io"
        }
        resp3 = self.client.post("/api/v2/incidents", json=payload_vip)
        self.assertEqual(resp3.status_code, 201)
        inc3 = resp3.json()
        # Normally 3/3 is P4; VIP caller escalates to P3
        self.assertEqual(inc3["priority"], "P3")
        self.assertTrue(any("VIP_CALLER_ESCALATED" in rule for rule in inc3.get("business_rules_applied", [])))

    def test_05_list_incidents_filtering(self):
        """Verify GET /api/v2/incidents supports multi-facet filtering and full-text search."""
        # List all
        r_all = self.client.get("/api/v2/incidents")
        self.assertEqual(r_all.status_code, 200)
        all_incs = r_all.json()
        self.assertIsInstance(all_incs, list)
        self.assertGreater(len(all_incs), 0)

        # Filter by state
        r_state = self.client.get("/api/v2/incidents?state=New")
        self.assertEqual(r_state.status_code, 200)
        for inc in r_state.json():
            self.assertEqual(inc["state"], "New")

        # Filter by priority
        r_prio = self.client.get("/api/v2/incidents?priority=P1")
        self.assertEqual(r_prio.status_code, 200)
        for inc in r_prio.json():
            self.assertEqual(inc["priority"], "P1")

        # Filter by category
        r_cat = self.client.get("/api/v2/incidents?category=Security")
        self.assertEqual(r_cat.status_code, 200)
        for inc in r_cat.json():
            self.assertEqual(inc["category"], "Security")

        # Search
        r_search = self.client.get("/api/v2/incidents?search=Checkout")
        self.assertEqual(r_search.status_code, 200)
        self.assertGreaterEqual(len(r_search.json()), 1)

    def test_06_incident_detail_and_sla_clock(self):
        """Verify GET /api/v2/incidents/{id} returns full detail, worklogs, subtasks, SLA clock, history."""
        # Create incident
        create_resp = self.client.post("/api/v2/incidents", json={
            "title": "API Gateway Latency Degradation",
            "category": "Cloud & Infrastructure",
            "subcategory": "Containers & Kubernetes",
            "item": "Ingress Controller 502 / 504",
            "impact": "2 - Medium",
            "urgency": "2 - Medium"
        })
        inc_id = create_resp.json()["id"]

        # Fetch detail
        detail_resp = self.client.get(f"/api/v2/incidents/{inc_id}")
        self.assertEqual(detail_resp.status_code, 200)
        data = detail_resp.json()
        self.assertEqual(data["id"], inc_id)
        self.assertIn("worklogs", data)
        self.assertIn("subtasks", data)
        self.assertIn("history", data)
        self.assertIn("sla_clock", data)
        self.assertIn("total_labor_cost", data)
        self.assertIn("total_minutes_logged", data)

        sla = data["sla_clock"]
        self.assertIn("target_hours", sla)
        self.assertIn("remaining_seconds", sla)
        self.assertIn("percentage_consumed", sla)
        self.assertIn("is_paused", sla)
        self.assertIn("is_breached", sla)

    def test_07_subtasks_lifecycle(self):
        """Verify POST /api/v2/incidents/{id}/tasks and PATCH /api/v2/incidents/{id}/tasks/{task_id}."""
        inc = self.client.post("/api/v2/incidents", json={
            "title": "Database Read Replica Out of Sync",
            "category": "Database",
            "subcategory": "Relational (Postgres/MySQL)",
            "impact": "2 - Medium",
            "urgency": "2 - Medium"
        }).json()
        inc_id = inc["id"]

        # 1. Add Subtask (POST 201)
        task_resp = self.client.post(f"/api/v2/incidents/{inc_id}/tasks", json={
            "title": "Check postgres replication lag via pg_stat_replication",
            "description": "Run lag check on db-replica-02",
            "assigned_to": "dba-engineer@opennow.io"
        })
        self.assertEqual(task_resp.status_code, 201)
        task_data = task_resp.json()
        self.assertEqual(task_data["incident_id"], inc_id)
        self.assertEqual(task_data["status"], "open")
        self.assertTrue(task_data["task_number"].startswith("TSK"))
        task_id = task_data["id"]

        # 2. Update Subtask status to in_progress (PATCH 200)
        patch_resp1 = self.client.patch(f"/api/v2/incidents/{inc_id}/tasks/{task_id}", json={
            "status": "in_progress"
        })
        self.assertEqual(patch_resp1.status_code, 200)
        self.assertEqual(patch_resp1.json()["status"], "in_progress")

        # 3. Update Subtask status to completed (PATCH 200)
        patch_resp2 = self.client.patch(f"/api/v2/incidents/{inc_id}/tasks/{task_id}", json={
            "status": "completed"
        })
        self.assertEqual(patch_resp2.status_code, 200)
        self.assertEqual(patch_resp2.json()["status"], "completed")

    def test_08_worklogs_and_total_cost(self):
        """Verify POST and GET /api/v2/incidents/{id}/worklogs and accurate labor cost summation."""
        inc = self.client.post("/api/v2/incidents", json={
            "title": "Memory leak investigation",
            "category": "Software",
            "subcategory": "Custom Services",
            "impact": "2 - Medium",
            "urgency": "2 - Medium"
        }).json()
        inc_id = inc["id"]

        # 1. Add Worklog 1: 60 minutes @ $75.00/hr = $75.00
        w1_resp = self.client.post(f"/api/v2/incidents/{inc_id}/worklogs", json={
            "technician": "Jordan Blake",
            "notes": "Heap dump capture and memory profiling",
            "minutes_spent": 60.0,
            "hourly_rate": 75.0
        })
        self.assertEqual(w1_resp.status_code, 201)
        w1 = w1_resp.json()
        self.assertEqual(w1["labor_cost"], 75.0)
        self.assertEqual(w1["total_labor_cost"], 75.0)
        self.assertEqual(w1["total_minutes_logged"], 60.0)

        # 2. Add Worklog 2: 30 minutes @ $80.00/hr = $40.00 (Total: $115.00)
        w2_resp = self.client.post(f"/api/v2/incidents/{inc_id}/worklogs", json={
            "technician": "Alex Morgan",
            "notes": "Code patch and hotfix deployment",
            "minutes_spent": 30.0,
            "hourly_rate": 80.0
        })
        self.assertEqual(w2_resp.status_code, 201)
        w2 = w2_resp.json()
        self.assertEqual(w2["labor_cost"], 40.0)
        self.assertEqual(w2["total_labor_cost"], 115.0)
        self.assertEqual(w2["total_minutes_logged"], 90.0)

        # 3. List worklogs (GET 200)
        list_resp = self.client.get(f"/api/v2/incidents/{inc_id}/worklogs")
        self.assertEqual(list_resp.status_code, 200)
        logs = list_resp.json()
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["technician"], "Jordan Blake")
        self.assertEqual(logs[1]["technician"], "Alex Morgan")

    def test_09_allowed_transitions_endpoint(self):
        """Verify GET /api/v2/incidents/{id}/allowed-transitions returns valid next states."""
        inc = self.client.post("/api/v2/incidents", json={
            "title": "Allowed transitions test ticket",
            "category": "Hardware",
            "impact": "3 - Low",
            "urgency": "3 - Low"
        }).json()
        inc_id = inc["id"]

        resp = self.client.get(f"/api/v2/incidents/{inc_id}/allowed-transitions")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["current_state"], "New")
        self.assertIn("Assigned", data["allowed_transitions"])
        self.assertIn("In Progress", data["allowed_transitions"])
        self.assertIn("Canceled", data["allowed_transitions"])
        self.assertNotIn("Closed", data["allowed_transitions"])

    def test_10_lifecycle_transition_guards(self):
        """Verify state transitions and strict validation guards:
        - Invalid transition rejection (400)
        - On Hold requires pause_reason (400 without, 200 with)
        - SLA clock pausing & resuming
        - Resolved requires resolution_code & root_cause (400 without, 200 with)
        - Active subtasks block resolution (400)
        - Resolved -> Closed
        - Closed is terminal (400)
        """
        inc = self.client.post("/api/v2/incidents", json={
            "title": "Lifecycle Transition Guard Verification",
            "category": "Database",
            "subcategory": "Relational (Postgres/MySQL)",
            "impact": "1 - High",
            "urgency": "1 - High"
        }).json()
        inc_id = inc["id"]

        # 1. Invalid transition: New -> Closed directly (Must be rejected with 400)
        r_inv = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "Closed"
        })
        self.assertEqual(r_inv.status_code, 400)
        self.assertIn("Invalid lifecycle transition", r_inv.json()["detail"])

        # 2. Valid transition: New -> In Progress (200)
        r_inp = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "In Progress",
            "actor": "lead-sre"
        })
        self.assertEqual(r_inp.status_code, 200)
        self.assertEqual(r_inp.json()["state"], "In Progress")

        # 3. Guard: Transition to On Hold WITHOUT pause_reason -> 400
        r_hold_fail = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "On Hold"
        })
        self.assertEqual(r_hold_fail.status_code, 400)
        self.assertIn("pause_reason", r_hold_fail.json()["detail"])

        # 4. Valid transition to On Hold WITH pause_reason -> 200, SLA paused
        r_hold_ok = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "On Hold",
            "pause_reason": "Awaiting Vendor"
        })
        self.assertEqual(r_hold_ok.status_code, 200)
        self.assertEqual(r_hold_ok.json()["state"], "On Hold")
        self.assertEqual(r_hold_ok.json()["pause_reason"], "Awaiting Vendor")
        self.assertTrue(r_hold_ok.json()["sla_clock"]["is_paused"])

        # 5. Resume from On Hold -> In Progress -> 200, SLA clock resumes
        r_resume = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "In Progress"
        })
        self.assertEqual(r_resume.status_code, 200)
        self.assertEqual(r_resume.json()["state"], "In Progress")
        self.assertFalse(r_resume.json()["sla_clock"]["is_paused"])

        # 6. Add open subtask to verify subtask guard on resolution
        subtask = self.client.post(f"/api/v2/incidents/{inc_id}/tasks", json={
            "title": "Vendor patch validation on staging",
            "assigned_to": "qa-engineer@opennow.io"
        }).json()
        subtask_id = subtask["id"]

        # 7. Guard: Attempt to Resolve WITH active subtask -> 400
        r_res_subtask_fail = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "Resolved",
            "resolution_code": "Solved (Permanently)",
            "root_cause": "Firmware deadlock"
        })
        self.assertEqual(r_res_subtask_fail.status_code, 400)
        self.assertIn("active subtasks", r_res_subtask_fail.json()["detail"])

        # Complete the subtask
        self.client.patch(f"/api/v2/incidents/{inc_id}/tasks/{subtask_id}", json={"status": "completed"})

        # 8. Guard: Attempt to Resolve WITHOUT resolution_code -> 400
        r_res_no_code = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "Resolved",
            "root_cause": "Firmware deadlock"
        })
        self.assertEqual(r_res_no_code.status_code, 400)
        self.assertIn("resolution_code", r_res_no_code.json()["detail"])

        # 9. Guard: Attempt to Resolve WITHOUT root_cause -> 400
        r_res_no_cause = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "Resolved",
            "resolution_code": "Solved (Permanently)"
        })
        self.assertEqual(r_res_no_cause.status_code, 400)
        self.assertIn("root_cause", r_res_no_cause.json()["detail"])

        # 10. Valid transition to Resolved -> 200
        r_res_ok = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "Resolved",
            "resolution_code": "Solved (Permanently)",
            "root_cause": "Firmware deadlock in SAS storage controller",
            "resolution_notes": "Upgraded SAS controller firmware to v4.2.1."
        })
        self.assertEqual(r_res_ok.status_code, 200)
        resolved_inc = r_res_ok.json()
        self.assertEqual(resolved_inc["state"], "Resolved")
        self.assertIsNotNone(resolved_inc["resolved_at"])

        # 11. Valid transition from Resolved -> Closed -> 200
        r_close = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "Closed"
        })
        self.assertEqual(r_close.status_code, 200)
        self.assertEqual(r_close.json()["state"], "Closed")
        self.assertIsNotNone(r_close.json()["closed_at"])

        # 12. Guard: Closed is terminal, cannot transition further -> 400
        r_terminal = self.client.post(f"/api/v2/incidents/{inc_id}/transition", json={
            "target_state": "In Progress"
        })
        self.assertEqual(r_terminal.status_code, 400)
        self.assertIn("Invalid lifecycle transition", r_terminal.json()["detail"])


if __name__ == "__main__":
    unittest.main()
