"""OpenNow Master Data Configuration Engine & Incident Runtime Reflection Test Suite
==================================================================================
Verifies that updates made via configuration REST endpoints immediately affect
runtime incident triage, taxonomy trees, priority matrix calculation, SLA due dates,
technician labor accounting, and automated business routing rules.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.api import app
from backend.config_engine import config_engine


class TestMasterDataRuntimeReflection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        config_engine.init_schema()
        config_engine.seed_defaults_if_empty()

    def test_01_taxonomy_runtime_reflection(self):
        """Verify adding taxonomy via /api/v2/config immediately reflects in /api/v2/incidents/taxonomy/tree."""
        # 1. Create new Category
        cat_res = self.client.post("/api/v2/config/taxonomy/categories", json={
            "name": "Observability & APM",
            "description": "Application Performance Monitoring and Distributed Tracing"
        })
        self.assertEqual(cat_res.status_code, 201)
        cat_id = cat_res.json()["id"]

        # 2. Create Subcategory
        sub_res = self.client.post("/api/v2/config/taxonomy/subcategories", json={
            "category_id": cat_id,
            "name": "Prometheus & Grafana",
            "description": "Metrics scraping and dashboard telemetry"
        })
        self.assertEqual(sub_res.status_code, 201)
        sub_id = sub_res.json()["id"]

        # 3. Create Item
        item_res = self.client.post("/api/v2/config/taxonomy/items", json={
            "subcategory_id": sub_id,
            "name": "Metric Ingestion Rate Limit Exceeded"
        })
        self.assertEqual(item_res.status_code, 201)
        item_id = item_res.json()["id"]

        # 4. Check runtime reflection in incident taxonomy tree
        tree_resp = self.client.get("/api/v2/incidents/taxonomy/tree")
        self.assertEqual(tree_resp.status_code, 200)
        tree = tree_resp.json()
        self.assertIn("Observability & APM", tree["category_names"])
        self.assertIn("Observability & APM", tree["taxonomy"])
        self.assertIn("Prometheus & Grafana", tree["taxonomy"]["Observability & APM"])
        self.assertIn("Metric Ingestion Rate Limit Exceeded", tree["taxonomy"]["Observability & APM"]["Prometheus & Grafana"])

        # 5. Toggle Category Inactive
        toggle_res = self.client.post(f"/api/v2/config/taxonomy/categories/{cat_id}/toggle-active")
        self.assertEqual(toggle_res.status_code, 200)
        self.assertFalse(toggle_res.json()["is_active"])

        # 6. Verify excluded from active incident taxonomy tree
        tree_after = self.client.get("/api/v2/incidents/taxonomy/tree").json()
        self.assertNotIn("Observability & APM", tree_after["category_names"])

        # Cleanup
        self.client.delete(f"/api/v2/config/taxonomy/items/{item_id}")
        self.client.delete(f"/api/v2/config/taxonomy/subcategories/{sub_id}")
        self.client.delete(f"/api/v2/config/taxonomy/categories/{cat_id}")

    def test_02_priority_matrix_runtime_reflection(self):
        """Verify updating Priority Matrix changes runtime priority calculation and new incident creation."""
        # 1. Check baseline (Impact 2, Urgency 1 -> default is P2, 4.0h)
        base_calc = self.client.post("/api/v2/incidents/priority-matrix/calculate", json={
            "impact": "2 - Medium",
            "urgency": "1 - High"
        }).json()
        self.assertEqual(base_calc["priority"], "P2")
        self.assertEqual(base_calc["sla_target_hours"], 4.0)

        # 2. Update Matrix cell (Impact 2, Urgency 1) -> P1-Escalated, 1.5h SLA
        upd_res = self.client.put("/api/v2/config/priority-matrix/2/1", json={
            "impact_level": 2,
            "urgency_level": 1,
            "priority_code": "P1",
            "priority_label": "P1 - Critical Accelerated",
            "resolution_sla_hours": 1.5,
            "response_sla_hours": 0.2
        })
        self.assertEqual(upd_res.status_code, 200)

        # 3. Verify immediate reflection in /priority-matrix/calculate
        new_calc = self.client.post("/api/v2/incidents/priority-matrix/calculate", json={
            "impact": "2 - Medium",
            "urgency": "1 - High"
        }).json()
        self.assertEqual(new_calc["priority"], "P1")
        self.assertEqual(new_calc["sla_target_hours"], 1.5)
        self.assertEqual(new_calc["priority_label"], "P1 - Critical Accelerated")

        # 4. Verify incident created with Impact 2, Urgency 1 receives P1 and 1.5h SLA target
        inc_res = self.client.post("/api/v2/incidents", json={
            "title": "Payment Microservice Connection Timeout",
            "category": "Software",
            "subcategory": "Custom Services",
            "item": "Microservice Connection Refused",
            "impact": "2 - Medium",
            "urgency": "1 - High",
            "caller": "checkout-service@opennow.io"
        })
        self.assertEqual(inc_res.status_code, 201)
        inc_data = inc_res.json()
        self.assertEqual(inc_data["priority"], "P1")
        self.assertEqual(inc_data["sla_target_hours"], 1.5)

        # 5. Restore matrix back to default P2, 4.0h
        self.client.put("/api/v2/config/priority-matrix/2/1", json={
            "impact_level": 2,
            "urgency_level": 1,
            "priority_code": "P2",
            "priority_label": "P2 - High",
            "resolution_sla_hours": 4.0,
            "response_sla_hours": 0.5
        })

    def test_03_business_rules_dynamic_routing(self):
        """Verify creating a dynamic business rule via config API routes new incidents immediately."""
        # 1. Create a custom routing rule for Payments & FinTech
        rule_res = self.client.post("/api/v2/config/business-rules", json={
            "name": "FinTech Payments Tier 1 Routing",
            "description": "Routes all checkout and stripe payment errors directly to FinTech Core SRE",
            "order_num": 15,
            "criteria": {"field": "title", "operator": "contains", "value": "Stripe"},
            "actions": {
                "assignment_group": "FinTech Core SRE",
                "priority": "P1"
            }
        })
        self.assertEqual(rule_res.status_code, 201)
        rule_id = rule_res.json()["id"]

        # 2. Post incident matching criteria
        ticket_res = self.client.post("/api/v2/incidents", json={
            "title": "Stripe Webhook Signature Verification Failed",
            "category": "Software",
            "impact": "3 - Low",
            "urgency": "3 - Low",
            "caller": "api-gateway@opennow.io"
        })
        self.assertEqual(ticket_res.status_code, 201)
        ticket = ticket_res.json()
        self.assertEqual(ticket["assignment_group"], "FinTech Core SRE")
        self.assertEqual(ticket["priority"], "P1")
        self.assertTrue(any("FINTECH_PAYMENTS_TIER_1_ROUTING" in r for r in ticket.get("business_rules_applied", [])))

        # Cleanup
        self.client.delete(f"/api/v2/config/business-rules/{rule_id}")

    def test_04_technician_rates_and_worklog_accounting(self):
        """Verify technician rate configured in master data is applied to labor cost calculations."""
        # 1. Create technician with rate $145/hr
        tech_res = self.client.post("/api/v2/config/technicians", json={
            "name": "Dr. Aris Thorne",
            "email": "aris.t@opennow.io",
            "hourly_rate": 145.0,
            "support_group": "Database Architecture",
            "role": "Principal DBA"
        })
        self.assertEqual(tech_res.status_code, 201)
        tech_id = tech_res.json()["id"]

        # 2. Create incident
        inc_res = self.client.post("/api/v2/incidents", json={
            "title": "Postgres connection pool deadlock",
            "category": "Database",
            "impact": "2 - Medium",
            "urgency": "2 - Medium"
        })
        inc_id = inc_res.json()["id"]

        # 3. Add worklog for Dr. Aris Thorne without explicitly overriding hourly_rate
        # 60 minutes at $145/hr = $145.00
        wl_res = self.client.post(f"/api/v2/incidents/{inc_id}/worklogs", json={
            "technician": "Dr. Aris Thorne",
            "notes": "Terminated blocking session and analyzed pg_stat_activity",
            "minutes_spent": 60.0
        })
        self.assertEqual(wl_res.status_code, 201)
        wl = wl_res.json()
        self.assertEqual(wl["hourly_rate"], 145.0)
        self.assertEqual(wl["labor_cost"], 145.0)

        # Cleanup
        self.client.delete(f"/api/v2/config/technicians/{tech_id}")

    def test_05_resolution_codes_and_root_cause_master_data(self):
        """Verify resolution codes full CRUD and retrieval."""
        res = self.client.post("/api/v2/config/resolution-codes", json={
            "code": "Database Shard Rebalanced",
            "category": "Database",
            "root_cause_options": ["Hot Key Skew", "Uneven Hash Distribution", "Node Drain Complete"],
            "description": "Database partitions rebalanced across storage nodes"
        })
        self.assertEqual(res.status_code, 201)
        rc_id = res.json()["id"]

        # Retrieve list
        codes_res = self.client.get("/api/v2/config/resolution-codes")
        self.assertEqual(codes_res.status_code, 200)
        codes = [c["code"] for c in codes_res.json()]
        self.assertIn("Database Shard Rebalanced", codes)

        # Cleanup
        self.client.delete(f"/api/v2/config/resolution-codes/{rc_id}")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMasterDataRuntimeReflection)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    if not res.wasSuccessful():
        sys.exit(1)
