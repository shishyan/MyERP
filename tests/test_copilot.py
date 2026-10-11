"""
Comprehensive Test Suite for OpenNow AI Co-Pilot
================================================
Tests:
1. Incident Triage Engine across multiple technical domains and priorities
2. CMDB Blast Radius and Root Cause Graph Analysis
3. Runbook Synthesizer for Postgres, Kubernetes, SSL, Payment, and generic incidents
4. Stakeholder & Technical Communications generation
5. FastAPI REST API endpoints
"""

import sys
import os
import unittest

# Ensure OpenNow root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_engine.copilot import (
    OpenNowCoPilot,
    IncidentTriageEngine,
    CMDBBlastRadiusEngine,
    RunbookSynthesizer,
    StakeholderCommunicationsEngine,
    TriageRequest,
    BlastRadiusRequest,
    RunbookRequest,
    CommunicationDraftRequest,
    copilot
)
from fastapi.testclient import TestClient
from backend.api import app


class TestIncidentTriage(unittest.TestCase):
    def setUp(self):
        self.triage = IncidentTriageEngine()

    def test_p1_outage_triage(self):
        req = TriageRequest(
            title="CRITICAL: Complete PostgreSQL Aurora cluster outage - checkout failing for all users",
            description="Our primary database is completely unresponsive. All transactions are aborting with connection timeout. Customers screaming and revenue blocked.",
            task_id="INC-9901"
        )
        res = self.triage.triage(req)
        
        self.assertEqual(res.priority_code, "P1")
        self.assertEqual(res.category, "Database")
        self.assertEqual(res.recommended_assignment_team, "Database Team")
        self.assertTrue(res.escalation_triggered)
        self.assertGreaterEqual(res.urgency_score, 0.8)
        self.assertLessEqual(res.sentiment_score, 0.4)
        self.assertEqual(res.impact_scope, "Enterprise-wide")
        
        # Check identified CIs
        ci_ids = [ci["ci_id"] for ci in res.identified_cis]
        self.assertIn("ci-db-postgres-primary", ci_ids)

    def test_p2_intermittent_payment_triage(self):
        req = TriageRequest(
            title="Intermittent 502 bad gateway on Stripe payment webhook integration",
            description="Payment worker pods experiencing high latency and connection pool spikes. Roughly 15% of checkout webhooks are failing.",
            task_id="INC-9902"
        )
        res = self.triage.triage(req)
        
        self.assertIn(res.priority_code, ["P1", "P2"])
        self.assertEqual(res.category, "Payment")
        self.assertEqual(res.recommended_assignment_team, "Payment Ops")
        ci_ids = [ci["ci_id"] for ci in res.identified_cis]
        self.assertIn("ci-payment-service", ci_ids)

    def test_p4_minor_cosmetic_triage(self):
        req = TriageRequest(
            title="Minor typo in settings button label on sandbox portal",
            description="In the staging test bench, the button says 'Submitt' instead of 'Submit'. Cosmetic defect only.",
            task_id="INC-9904"
        )
        res = self.triage.triage(req)
        
        self.assertEqual(res.priority_code, "P4")
        self.assertFalse(res.escalation_triggered)
        self.assertLess(res.urgency_score, 0.5)

    def test_security_breach_auto_escalation(self):
        req = TriageRequest(
            title="Suspicious token leak and potential unauthorized credential exfiltration detected in audit logs",
            description="Automated SIEM alerted that API tokens for service accounts were exposed in public logs.",
            task_id="INC-9905"
        )
        res = self.triage.triage(req)
        
        self.assertEqual(res.category, "Security")
        self.assertEqual(res.recommended_assignment_team, "SecOps")
        self.assertTrue(res.escalation_triggered)


class TestCMDBBlastRadius(unittest.TestCase):
    def setUp(self):
        self.engine = CMDBBlastRadiusEngine()

    def test_postgres_primary_blast_radius(self):
        req = BlastRadiusRequest(ci_id="ci-db-postgres-primary")
        res = self.engine.analyze_blast_radius(req)

        self.assertEqual(res.target_ci["ci_id"], "ci-db-postgres-primary")
        self.assertEqual(res.target_ci["tier"], "Tier 1")
        
        # Verify downstream affected nodes include auth, payment, order, customer-web
        downstream_ids = [n.ci_id for n in res.downstream_blast_radius]
        self.assertIn("ci-auth-service", downstream_ids)
        self.assertIn("ci-payment-service", downstream_ids)
        self.assertIn("ci-order-service", downstream_ids)
        self.assertIn("ci-customer-web", downstream_ids)

        # Risk score should be CRITICAL
        self.assertGreaterEqual(res.system_risk_score, 80)
        self.assertEqual(res.risk_level, "CRITICAL")
        self.assertIn("Customer Checkout & Revenue Processing", res.critical_business_operations)

        # Upstream should include AWS cloud VPC
        upstream_ids = [n.ci_id for n in res.upstream_dependencies]
        self.assertIn("ci-cloud-aws-us-east", upstream_ids)

    def test_isolated_leaf_ci_blast_radius(self):
        req = BlastRadiusRequest(ci_id="ci-analytics-pipeline")
        res = self.engine.analyze_blast_radius(req)

        # Analytics pipeline has no downstream dependents
        self.assertEqual(len(res.downstream_blast_radius), 0)
        self.assertIn(res.risk_level, ["LOW", "MEDIUM"])
        self.assertLess(res.system_risk_score, 50)


class TestRunbookSynthesizer(unittest.TestCase):
    def setUp(self):
        self.synthesizer = RunbookSynthesizer()

    def test_postgres_lock_runbook(self):
        req = RunbookRequest(
            title="Deadlock and connection limit reached on Postgres DB",
            category="Database"
        )
        res = self.synthesizer.synthesize(req)

        self.assertEqual(res.category, "Database")
        self.assertIn("PostgreSQL", res.runbook_title)
        self.assertTrue(any("pg_stat_activity" in s.command or "" for s in res.steps))
        self.assertTrue(any("pg_cancel_backend" in s.command or "" for s in res.steps))

    def test_k8s_crashloop_runbook(self):
        req = RunbookRequest(
            title="Ingress pods CrashLoopBackOff",
            category="Infrastructure"
        )
        res = self.synthesizer.synthesize(req)

        self.assertEqual(res.category, "Infrastructure")
        self.assertIn("CrashLoopBackOff", res.runbook_title)
        self.assertTrue(any("rollout undo" in s.command or "" for s in res.steps))

    def test_ssl_renewal_runbook(self):
        req = RunbookRequest(
            title="TLS Certificate Expired for opennow.io domain",
            category="Security"
        )
        res = self.synthesizer.synthesize(req)

        self.assertEqual(res.category, "Security")
        self.assertIn("Certificate", res.runbook_title)
        self.assertTrue(any("openssl" in s.command or "" for s in res.steps))


class TestStakeholderCommunications(unittest.TestCase):
    def setUp(self):
        self.engine = StakeholderCommunicationsEngine()

    def test_stakeholder_outage_draft(self):
        req = CommunicationDraftRequest(
            task_id="INC-1001",
            title="Customer Checkout Service Degradation",
            audience="stakeholder",
            phase="investigating"
        )
        res = self.engine.draft(req)

        self.assertEqual(res.audience, "stakeholder")
        self.assertIn("Investigating", res.subject)
        self.assertIn("Incident Notification", res.body_markdown)
        self.assertIn("StatusPage", res.target_channels)

    def test_technical_mitigated_draft(self):
        req = CommunicationDraftRequest(
            task_id="INC-1001",
            title="Postgres Connection Leak",
            audience="technical",
            phase="mitigated",
            ci_id="ci-db-postgres-primary",
            details="Rolled out connection pool fix and cycled PgBouncer."
        )
        res = self.engine.draft(req)

        self.assertEqual(res.audience, "technical")
        self.assertIn("TECHNICAL UPDATE", res.subject)
        self.assertIn("SRE / DEVOPS INCIDENT UPDATE", res.body_markdown)
        self.assertIn("#sre-alerts", res.target_channels)


class TestFastAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.database import db
        if not db.get_task_by_number("INC000101"):
            db.seed_data()
        cls.client = TestClient(app)

    def setUp(self):
        self.client = self.__class__.client

    def test_health_endpoint(self):
        resp = self.client.get("/api/ai/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertGreater(data["cmdb_nodes_loaded"], 0)

    def test_post_triage_api(self):
        payload = {
            "title": "Severe latency and 504 timeouts on User Auth Service",
            "description": "All customer logins are failing with gateway timeouts. Auth service pod CPU pegged at 100%."
        }
        resp = self.client.post("/api/ai/triage", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data["priority_code"], ["P1", "P2"])
        self.assertIn("Auth", data["identified_cis"][0]["name"])

    def test_post_blast_radius_api(self):
        payload = {"ci_id": "ci-payment-service"}
        resp = self.client.post("/api/ai/blast-radius", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["target_ci"]["ci_id"], "ci-payment-service")
        self.assertGreaterEqual(data["system_risk_score"], 60)

    def test_post_generate_runbook_api(self):
        payload = {"task_id": "INC-1001"}
        resp = self.client.post("/api/ai/generate-runbook", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["task_id"], "INC-1001")
        self.assertIn("PostgreSQL", data["runbook_title"])

    def test_post_draft_communication_api(self):
        payload = {
            "task_id": "INC-1001",
            "audience": "stakeholder",
            "phase": "resolved"
        }
        resp = self.client.post("/api/ai/draft-communication", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("RESOLVED", data["subject"])

    def test_db_task_runbook_integration(self):
        # Query runbook for database-seeded incident INC000101
        payload = {"task_id": "INC000101"}
        resp = self.client.post("/api/ai/generate-runbook", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["task_id"], "INC000101")
        self.assertIn("Payment", data["runbook_title"])

    def test_numeric_ci_blast_radius(self):
        # Dynamically fetch PostgreSQL Primary CI id from SQLite database
        from backend.database import db
        pg_ci = next((c for c in db.list_cis() if "PostgreSQL Primary" in c["name"]), None)
        ci_id = str(pg_ci["id"]) if pg_ci else "ci-db-postgres-primary"
        payload = {"ci_id": ci_id}
        resp = self.client.post("/api/ai/blast-radius", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["system_risk_score"], 60)
        self.assertIn(data["risk_level"], ["HIGH", "CRITICAL"])

    def test_cmdb_catalog_endpoint(self):
        resp = self.client.get("/api/ai/cmdb/catalog")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("nodes", data)
        self.assertIn("relationships", data)
        self.assertGreater(len(data["nodes"]), 0)


if __name__ == "__main__":
    unittest.main()
