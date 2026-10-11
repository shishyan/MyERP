"""OpenNow Test Suite
Comprehensive unit and integration test coverage for data models, dynamic schema database,
automation engine, universal migration engine, and REST API.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.api import app
from backend.automation import AutomationEngine
from backend.database import DatabaseManager
from backend.migration_engine import MigrationEngine
from backend.models import (
    CIType,
    Environment,
    HealthStatus,
    Priority,
    RelationshipType,
    TaskCreate,
    TaskStatus,
    TaskType,
)


class TestOpenNowCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary SQLite database for testing
        cls.test_db_fd, cls.test_db_path = tempfile.mkstemp(suffix=".db")
        cls.db = DatabaseManager(db_path=cls.test_db_path)
        cls.db.seed_data()

        # Point backend modules to test database instance
        import backend.api
        import backend.database
        import backend.migration_engine

        backend.api.db = cls.db
        backend.database.db = cls.db
        backend.migration_engine.db = cls.db
        backend.migration_engine.migration_engine.db = cls.db

        # Wire test client
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        os.close(cls.test_db_fd)
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    # --- 1. Model Validation Tests ---

    def test_task_model_validation(self):
        task_data = {
            "title": "Auth API Gateway 502 Bad Gateway",
            "description": "Incoming requests failing at Envoy mesh.",
            "task_type": TaskType.INCIDENT,
            "priority": Priority.P1,
            "custom_fields": {"environment": "prod", "impact": "high"},
        }
        task_create = TaskCreate(**task_data)
        self.assertEqual(task_create.title, "Auth API Gateway 502 Bad Gateway")
        self.assertEqual(task_create.priority, Priority.P1)
        self.assertEqual(task_create.custom_fields["impact"], "high")

    # --- 2. Database CRUD & Dynamic Schema Tests ---

    def test_database_task_crud_and_json(self):
        # Create task
        task = self.db.create_task({
            "title": "Test Custom Fields Query Task",
            "description": "Validating JSON1 extract queries.",
            "task_type": TaskType.INCIDENT.value,
            "priority": Priority.P2.value,
            "caller": "tester@opennow.io",
            "custom_fields": {
                "datacenter": "us-west-2",
                "cluster_version": "v1.28.4",
                "customer_facing": True,
            },
        })
        self.assertIsNotNone(task["id"])
        self.assertTrue(task["task_number"].startswith("INC"))
        self.assertEqual(task["custom_fields"]["datacenter"], "us-west-2")

        # Query by custom field
        results = self.db.query_tasks_by_custom_field("datacenter", "us-west-2")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["custom_fields"]["datacenter"], "us-west-2")

        # Update task
        updated = self.db.update_task(
            task["id"],
            {"status": TaskStatus.IN_PROGRESS.value, "assigned_to": "engineer@opennow.io"},
            author="tester@opennow.io",
        )
        self.assertEqual(updated["status"], TaskStatus.IN_PROGRESS.value)
        self.assertEqual(updated["assigned_to"], "engineer@opennow.io")

        # Check activity logs
        activities = self.db.get_activities_for_task(task["id"])
        self.assertGreaterEqual(len(activities), 2)  # creation + status update

    def test_cmdb_graph_and_cis(self):
        # Verify seeded CIs
        cis = self.db.list_cis()
        self.assertEqual(len(cis), 10)

        # Retrieve graph
        graph = self.db.get_cmdb_graph()
        self.assertEqual(len(graph["nodes"]), 10)
        self.assertGreaterEqual(len(graph["edges"]), 10)

        # Verify specific relationship
        edge = graph["edges"][0]
        self.assertIn("source", edge)
        self.assertIn("target", edge)
        self.assertIn("relationship_type", edge)

    def test_operational_stats_metrics(self):
        stats = self.db.get_metrics_and_stats()
        self.assertIn("total_tasks", stats)
        self.assertIn("total_open", stats)
        self.assertIn("p1_critical_count", stats)
        self.assertIn("mttr_hours", stats)
        self.assertIn("sla_compliance_rate", stats)
        self.assertGreater(stats["total_tasks"], 0)
        self.assertGreater(stats["sla_compliance_rate"], 0.0)

    # --- 3. Automation Engine Tests ---

    def test_automation_sla_calculation(self):
        p1_sla = AutomationEngine.calculate_sla_due("P1")
        p4_sla = AutomationEngine.calculate_sla_due("P4")
        self.assertIsNotNone(p1_sla)
        self.assertIsNotNone(p4_sla)

    def test_automation_p1_triage_rule(self):
        eval_payload = {
            "title": "Payment gateway down",
            "task_type": "incident",
            "priority": "P1",
            "caller": "monitoring@opennow.io",
        }
        res = AutomationEngine.evaluate_task_creation(eval_payload)
        self.assertEqual(res["mutations"].get("assigned_team"), "Site Reliability Engineering")
        self.assertTrue(len(res["generated_activities"]) > 0)

    # --- 4. Universal Migration Engine Tests ---

    def test_migration_samples(self):
        snow_sample = MigrationEngine.get_sample_data("servicenow")
        self.assertEqual(snow_sample["sample_id"], "servicenow")
        self.assertIn("INC009101", snow_sample["file_content"])

        jira_sample = MigrationEngine.get_sample_data("jira")
        self.assertEqual(jira_sample["sample_id"], "jira")
        self.assertEqual(jira_sample["format"], "json")

        glpi_sample = MigrationEngine.get_sample_data("glpi")
        self.assertEqual(glpi_sample["sample_id"], "glpi")

    def test_migration_analyze_and_execute(self):
        snow_sample = MigrationEngine.get_sample_data("servicenow")
        analysis = MigrationEngine.analyze_and_plan(
            file_content=snow_sample["file_content"],
            file_name=snow_sample["file_name"],
        )
        self.assertTrue(analysis["success"])
        self.assertEqual(analysis["record_count"], 5)
        self.assertIn("incident", analysis.get("detected_entity_type", "incident"))
        self.assertGreaterEqual(len(analysis["mappings"]), 4)
        self.assertEqual(len(analysis["preview_records"]), 3)

        # Execute migration
        res = MigrationEngine.execute_migration(
            file_content=snow_sample["file_content"],
            file_name=snow_sample["file_name"],
            db_manager=self.db,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["imported_count"], 5)
        self.assertEqual(len(res["errors"]), 0)

    # --- 5. FastAPI REST API Endpoint Tests ---

    def test_api_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")

    def test_api_tasks_list_and_filter(self):
        # List all
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        tasks = response.json()
        self.assertIsInstance(tasks, list)
        self.assertGreater(len(tasks), 0)

        # Filter by priority
        response = self.client.get("/api/tasks?priority=P1")
        self.assertEqual(response.status_code, 200)
        p1_tasks = response.json()
        for t in p1_tasks:
            self.assertEqual(t["priority"], "P1")

        # Search
        response = self.client.get("/api/tasks?search=PostgreSQL")
        self.assertEqual(response.status_code, 200)
        search_tasks = response.json()
        self.assertGreater(len(search_tasks), 0)

    def test_api_task_lifecycle(self):
        # 1. Create Task
        payload = {
            "title": "API Test Task Creation",
            "description": "Testing full REST lifecycle.",
            "task_type": "incident",
            "priority": "P2",
            "status": "new",
            "caller": "api-tester@opennow.io",
            "assigned_team": "IT Operations",
            "custom_fields": {"client": "Postman", "automated": True},
        }
        res = self.client.post("/api/tasks", json=payload)
        self.assertEqual(res.status_code, 201)
        created = res.json()
        task_id = created["id"]
        self.assertTrue(created["task_number"].startswith("INC"))

        # 2. Get Task Detail
        res = self.client.get(f"/api/tasks/{task_id}")
        self.assertEqual(res.status_code, 200)
        detail = res.json()
        self.assertIn("task", detail)
        self.assertIn("activity_logs", detail)
        self.assertIn("affected_cis", detail)

        # 3. Patch Task
        patch_payload = {
            "status": "in_progress",
            "assigned_to": "lead-sre@opennow.io",
        }
        res = self.client.patch(f"/api/tasks/{task_id}", json=patch_payload)
        self.assertEqual(res.status_code, 200)
        updated = res.json()
        self.assertEqual(updated["status"], "in_progress")
        self.assertEqual(updated["assigned_to"], "lead-sre@opennow.io")

        # 4. Add Activity
        act_payload = {
            "author": "lead-sre@opennow.io",
            "message": "Mitigation steps executed. Traffic returned to normal.",
            "activity_type": "comment",
        }
        res = self.client.post(f"/api/tasks/{task_id}/activities", json=act_payload)
        self.assertEqual(res.status_code, 201)
        act = res.json()
        self.assertEqual(act["author"], "lead-sre@opennow.io")

    def test_api_cmdb_endpoints(self):
        # List CIs
        res = self.client.get("/api/cmdb/cis")
        self.assertEqual(res.status_code, 200)
        cis = res.json()
        self.assertGreater(len(cis), 0)

        # Topology graph
        res = self.client.get("/api/cmdb/graph")
        self.assertEqual(res.status_code, 200)
        graph = res.json()
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)

        # Get CI detail
        ci_id = cis[0]["id"]
        res = self.client.get(f"/api/cmdb/cis/{ci_id}")
        self.assertEqual(res.status_code, 200)
        ci_detail = res.json()
        self.assertIn("ci", ci_detail)
        self.assertIn("affected_tasks", ci_detail)
        self.assertIn("dependencies", ci_detail)

    def test_api_stats_endpoint(self):
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)
        stats = res.json()
        self.assertIn("total_tasks", stats)
        self.assertIn("total_open", stats)
        self.assertIn("p1_critical_count", stats)
        self.assertIn("mttr_hours", stats)
        self.assertIn("sla_compliance_rate", stats)

    def test_api_migration_endpoints(self):
        # 1. Sample endpoint
        res = self.client.get("/api/migration/samples/servicenow")
        self.assertEqual(res.status_code, 200)
        sample = res.json()
        self.assertEqual(sample["sample_id"], "servicenow")

        # 2. Analyze endpoint via JSON body
        res = self.client.post(
            "/api/migration/analyze",
            json={
                "file_content": sample["file_content"],
                "file_name": sample["file_name"],
            },
        )
        self.assertEqual(res.status_code, 200)
        plan = res.json()
        self.assertTrue(plan["success"])
        self.assertEqual(plan["record_count"], 5)

        # 3. Execute endpoint
        res = self.client.post(
            "/api/migration/execute",
            json={
                "file_content": sample["file_content"],
                "file_name": sample["file_name"],
            },
        )
        self.assertEqual(res.status_code, 200)
        exec_res = res.json()
        self.assertTrue(exec_res["success"])
        self.assertEqual(exec_res["imported_count"], 5)


if __name__ == "__main__":
    unittest.main()
