"""OpenNow Company DNA & Industry Blueprint Engine
==================================================
Adaptive enterprise configuration, layout, and governance engine.
Tailors 3-tier taxonomies, CMDB configuration items, SLA compliance,
financial downtime costing, and page designs based on the company's
industry, sub-industry, primary offering, and technology stack archetype.

Supported Enterprise Blueprints:
1. FinTech, Banking & Capital Markets (PCI-DSS Level 1, Ledgers, Clearing)
2. Healthcare & Life Sciences (HIPAA, Patient Safety, EHR/PACS)
3. E-Commerce, Retail & Logistics (GMV Outage, Real-Time Inventory, Cart)
4. Cloud Tech, Developer SaaS & Autonomous AI (GPU Clusters, Vector DB, mTLS)
5. Manufacturing & Industrial IoT (SCADA, ISA-95, PLC Robotics)
6. Telecommunications & 5G Carrier Operations (5G Packet Core, BGP, E911)
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.database import db

logger = logging.getLogger("opennow.industry_engine")

industry_router = APIRouter(prefix="/api/v2/industry", tags=["Industry & Company DNA Engine"])

# ============================================================================
# COMPREHENSIVE ENTERPRISE BLUEPRINTS CATALOG
# ============================================================================

INDUSTRY_BLUEPRINTS: Dict[str, Dict[str, Any]] = {
    "fintech": {
        "id": "fintech",
        "name": "FinTech, Banking & Capital Markets",
        "icon": "🏦",
        "sub_industries": [
            "Payment Processing & Acquirer Gateway",
            "Neo-Banking & Core Ledger Banking",
            "WealthTech & Algorithmic Trading",
            "Lending, Credit & Mortgage Underwriting",
            "Crypto Custody & Institutional Blockchain"
        ],
        "primary_offering": "High-Throughput Payment Authorization Rails & Settlement Ledger",
        "tech_stack": "Kafka Event Bus, PostgreSQL Aurora, Redis Cache, AWS GovCloud, Cloudflare Anycast, PCI-DSS HSMs",
        "compliance_standard": "PCI-DSS Level 1 • SOC 1/2 • GLBA • ISO 20022",
        "downtime_cost_per_minute": 18500.0,
        "layout_theme": "theme-fintech-sapphire",
        "badge_text": "🔒 PCI-DSS Level 1 Banking Mode",
        "sla_p1_resolve_hours": 0.5,
        "sla_p1_response_mins": 5,
        "taxonomies": {
            "Payment Rails & Clearing": {
                "Card Ingress & 3DS": ["3DS OTP Challenge Drop", "Issuer BIN Routing Timeout", "Stripe API Rate Limiting", "Acquirer Authorization Spike"],
                "ACH & Wire Clearing": ["FedNow Instant Settlement Failure", "SWIFT MT103 Parsing Error", "Batch Clearing File Malformed"],
                "Dispute & Chargeback Engine": ["Chargeback Arbitration Freeze", "Evidence Upload Webhook Failure"]
            },
            "Core Ledger & Accounts": {
                "Double-Entry Accounting": ["Ledger Imbalance Detected", "Double-Spend Prevention Lock", "Idempotency Key Conflict"],
                "Interest & Fee Engine": ["Daily Accrual Cron Hang", "Fee Calculation Precision Overflow"]
            },
            "Security & Cryptography": {
                "Hardware Security Module (HSM)": ["HSM Master Key Rotation Timeout", "CVV/PIN Decryption Latency Spike"],
                "Fraud & AML Detection": ["Transaction Anomaly False Positive Surge", "OFAC Sanctions List Sync Error"]
            }
        },
        "cmdb_nodes": [
            {"id": "CI-FIN-001", "name": "Core Banking Ledger Primary", "type": "database", "tier": "Tier 1 Mission Critical", "provider": "AWS GovCloud (us-gov-east-1)", "health": "healthy"},
            {"id": "CI-FIN-002", "name": "Payment Authorization Ingress Gateway", "type": "microservice", "tier": "Tier 1 Financial Rail", "provider": "AWS ALB Ingress", "health": "healthy"},
            {"id": "CI-FIN-003", "name": "Thales Luna HSM Encryption Vault", "type": "hardware_security", "tier": "Tier 1 PCI Vault", "provider": "Equinix Datacenter", "health": "healthy"},
            {"id": "CI-FIN-004", "name": "Kafka Financial Event Bus Cluster", "type": "event_stream", "tier": "Tier 1 Streaming", "provider": "Confluent Cloud", "health": "healthy"},
            {"id": "CI-FIN-005", "name": "Fraud Sentinel ML Scoring Engine", "type": "ai_inference", "tier": "Tier 2 Fraud Ops", "provider": "AWS SageMaker", "health": "healthy"}
        ]
    },
    "healthcare": {
        "id": "healthcare",
        "name": "Healthcare & Life Sciences",
        "icon": "🏥",
        "sub_industries": [
            "Hospital EHR/EMR Clinical Operations",
            "Telehealth & Virtual Care Delivery",
            "Medical Device & IoMT Sensor Grid",
            "Bioinformatics & Pharma Drug Discovery",
            "Medical Imaging PACS / DICOM Cloud"
        ],
        "primary_offering": "Zero-Downtime Clinical EHR Interoperability & Diagnostic PACS",
        "tech_stack": "HIPAA-Compliant Cloud, HL7/FHIR v4 Engine, Epic/Cerner Interface, DICOM PACS Storage, Kubernetes Edge",
        "compliance_standard": "HIPAA • HITECH • FDA 21 CFR Part 11 • Joint Commission",
        "downtime_cost_per_minute": 24000.0,
        "layout_theme": "theme-healthcare-clinical",
        "badge_text": "🏥 HIPAA Compliant • Patient Safety Mode",
        "sla_p1_resolve_hours": 0.5,
        "sla_p1_response_mins": 5,
        "taxonomies": {
            "Clinical EHR & EMR Systems": {
                "Epic / Cerner FHIR Bridge": ["HL7 MLLP Inbound Port Stall", "Patient Chart EHR Lock Contention", "FHIR v4 Bundle Deserialization Failure"],
                "Clinical Decision Support (CDS)": ["Medication Allergy Alert Suppression", "Drug-Drug Interaction Rule Timeout"]
            },
            "Medical Imaging & Diagnostics": {
                "PACS / DICOM Image Router": ["DICOM C-STORE Retrieval Latency", "CT Scan Image Archival Stall", "Radiology PACS Cache Eviction"],
                "Laboratory Information (LIS)": ["Specimen Barcode Scan Reject", "Analyzer Result Webhook Drop"]
            },
            "Patient Safety & Telehealth": {
                "IoMT Patient Monitoring Grid": ["ICU Vitals Telemetry Dropout", "Cardiac Telemetry Alert Delay"],
                "Virtual Video Consult": ["WebRTC HIPAA Signaling Flap", "Prescription e-Signature Drop"]
            }
        },
        "cmdb_nodes": [
            {"id": "CI-MED-001", "name": "Epic FHIR Interoperability Gateway", "type": "microservice", "tier": "Tier 1 Patient Safety", "provider": "HIPAA Isolated VPC", "health": "healthy"},
            {"id": "CI-MED-002", "name": "PACS Radiology Medical Imaging Server", "type": "storage_cluster", "tier": "Tier 1 Diagnostic", "provider": "PureStorage FlashBlade", "health": "healthy"},
            {"id": "CI-MED-003", "name": "ICU Bedside Telemetry IoT Broker", "type": "edge_gateway", "tier": "Tier 1 Life Safety", "provider": "Edge Kubernetes", "health": "healthy"},
            {"id": "CI-MED-004", "name": "Clinical Decision Support Engine", "type": "microservice", "tier": "Tier 1 Clinical", "provider": "AWS HealthLake", "health": "healthy"}
        ]
    },
    "retail": {
        "id": "retail",
        "name": "E-Commerce, Omnichannel Retail & Logistics",
        "icon": "🛒",
        "sub_industries": [
            "Global D2C Marketplace Platform",
            "Omnichannel Retail & Point-of-Sale (POS)",
            "Automated Warehousing & Robotics (WMS)",
            "Last-Mile Freight & Cold-Chain Logistics"
        ],
        "primary_offering": "High-Conversion Multi-Tenant Checkout & Real-Time Global Inventory Allocation",
        "tech_stack": "Cloudflare Global Edge, Elasticsearch / OpenSearch, Kafka, Snowflake, Stripe/Adyen, Kubernetes EKS",
        "compliance_standard": "PCI-DSS • SOC 2 • Black Friday Peak Readiness",
        "downtime_cost_per_minute": 14000.0,
        "layout_theme": "theme-retail-gmv",
        "badge_text": "🛒 GMV Outage Protection • Peak Traffic Mode",
        "sla_p1_resolve_hours": 1.0,
        "sla_p1_response_mins": 10,
        "taxonomies": {
            "Storefront & Checkout Cart": {
                "Shopping Cart & Checkout API": ["Cart Session Dropoff Surge", "Coupon / Promotion Calculation Timeout", "3DS Payment Gateway 504 Spike"],
                "Product Search & Catalog": ["Elasticsearch Indexing Lag", "Faceted Search Latency Spike", "Zero-Search Results Bug"]
            },
            "Inventory & Order Allocation": {
                "Real-Time Stock Allocator": ["Oversell Inventory Race Condition", "Safety Stock Lock Exhaustion", "Warehouse Routing Misallocation"],
                "WMS Robot Fulfillment": ["Warehouse Picking Scanner Drop", "Automated Conveyor PLC Timeout"]
            },
            "Shipping & Last Mile Logistics": {
                "Carrier Rate API Router": ["FedEx/UPS Label Generation Stall", "Tracking Webhook Ingestion Backpressure"]
            }
        },
        "cmdb_nodes": [
            {"id": "CI-RET-001", "name": "Global Checkout & Cart Microservice", "type": "microservice", "tier": "Tier 1 GMV Engine", "provider": "AWS EKS (us-east-1)", "health": "healthy"},
            {"id": "CI-RET-002", "name": "Elasticsearch Product Catalog Cluster", "type": "search_cluster", "tier": "Tier 1 Storefront", "provider": "Elastic Cloud", "health": "healthy"},
            {"id": "CI-RET-003", "name": "Real-Time Inventory Allocation Redis", "type": "cache_cluster", "tier": "Tier 1 Inventory", "provider": "Redis Enterprise", "health": "healthy"},
            {"id": "CI-RET-004", "name": "WMS Automated Robotics Dispatcher", "type": "edge_controller", "tier": "Tier 2 Warehouse", "provider": "Private Edge", "health": "healthy"}
        ]
    },
    "saas_ai": {
        "id": "saas_ai",
        "name": "Cloud Tech, Developer SaaS & Autonomous AI",
        "icon": "🚀",
        "sub_industries": [
            "Autonomous AI & LLM Cloud Infrastructure",
            "Developer Platforms & DevOps Tooling",
            "Cybersecurity & Threat Detection SaaS",
            "B2B Multi-Tenant Enterprise Software"
        ],
        "primary_offering": "Ultra-Low Latency LLM Inference, Vector Search & High-Velocity API Mesh",
        "tech_stack": "Kubernetes EKS, NVIDIA H100 GPU Clusters, PyTorch/vLLM, Qdrant/Milvus, Envoy Service Mesh, PostgreSQL",
        "compliance_standard": "SOC 2 Type II • ISO 27001 • FedRAMP High",
        "downtime_cost_per_minute": 11000.0,
        "layout_theme": "theme-saas-developer",
        "badge_text": "⚡ Autonomous AI SRE • SOC2 Audit Mode",
        "sla_p1_resolve_hours": 1.0,
        "sla_p1_response_mins": 10,
        "taxonomies": {
            "AI & LLM Inference Infrastructure": {
                "GPU Compute Fleet": ["NVIDIA CUDA Kernel Panic", "GPU Memory Leak / OOM Eviction", "vLLM PagedAttention Worker Desync"],
                "Vector Database & Embeddings": ["Qdrant HNSW Index Degradation", "Embedding API Dimensional Mismatch", "Vector Retrieval Latency Spike"]
            },
            "API Gateway & Auth Mesh": {
                "Envoy Ingress & Rate Limiter": ["API Gateway Worker Thread Core Dump", "mTLS Certificate Auto-Renewal Expired"],
                "Multi-Tenant Tenant Isolation": ["Cross-Tenant Cache Contamination", "Tenant Rate Limit Bypass Alert"]
            },
            "Data Pipeline & Streaming": {
                "Kafka & Flink Event Streaming": ["Kafka Consumer Group Lag Surge", "Flink Checkpoint Timeout Stall"]
            }
        },
        "cmdb_nodes": [
            {"id": "CI-AI-001", "name": "NVIDIA H100 GPU Tensor Cluster (Fleet A)", "type": "gpu_cluster", "tier": "Tier 1 AI Compute", "provider": "CoreWeave Cloud", "health": "healthy"},
            {"id": "CI-AI-002", "name": "Qdrant Distributed Vector Database", "type": "vector_db", "tier": "Tier 1 Semantic Search", "provider": "Kubernetes Dedicated", "health": "healthy"},
            {"id": "CI-AI-003", "name": "Envoy Multi-Tenant Ingress Router", "type": "api_gateway", "tier": "Tier 1 Edge", "provider": "AWS NLB + Envoy", "health": "healthy"},
            {"id": "CI-AI-004", "name": "PostgreSQL Multi-Tenant Shard Primary", "type": "database", "tier": "Tier 1 Relational", "provider": "AWS RDS Aurora", "health": "healthy"}
        ]
    },
    "manufacturing": {
        "id": "manufacturing",
        "name": "Manufacturing & Industrial IoT",
        "icon": "🏭",
        "sub_industries": [
            "Automotive Assembly & EV Gigafactories",
            "Aerospace Precision Manufacturing",
            "Semiconductor Cleanroom Fabrication",
            "Smart Packaging & Industrial Robotics"
        ],
        "primary_offering": "Real-Time SCADA Operations, PLC Robotics Orchestration & Predictive Maintenance",
        "tech_stack": "MQTT Sparkplug B, OPC-UA Gateways, Siemens S7 / Rockwell PLCs, TimescaleDB, Industrial Private 5G",
        "compliance_standard": "ISA-95 • ISO 9001 • OSHA Safety Interlock Standard",
        "downtime_cost_per_minute": 26000.0,
        "layout_theme": "theme-manufacturing-industrial",
        "badge_text": "🏭 Plant Safety & SCADA ISA-95 Mode",
        "sla_p1_resolve_hours": 0.5,
        "sla_p1_response_mins": 5,
        "taxonomies": {
            "Plant Floor & SCADA Control": {
                "SCADA Master Controller": ["SCADA Telemetry Dropout", "OPC-UA Server Connection Reset", "Historian Database Ingestion Backlog"],
                "PLC Robotics & Assembly Line": ["PLC Emergency Stop Interlock Triggered", "Robotic Arm Servo Position Desync", "Conveyor Belt Motor VFD Fault"]
            },
            "Industrial IoT & Sensors": {
                "MQTT Sensor Telemetry Grid": ["Vibration Sensor Threshold Alarm", "Thermal Camera Overheat Warning", "Industrial Private 5G Packet Loss"],
                "Quality Inspection Vision AI": ["Defect Detection Camera Offline", "Vision AI False Rejection Surge"]
            },
            "Supply Chain & MES Systems": {
                "Manufacturing Execution (MES)": ["Work-in-Progress (WIP) Tracking Stall", "Bill-of-Materials (BOM) Sync Error"]
            }
        },
        "cmdb_nodes": [
            {"id": "CI-MFG-001", "name": "SCADA Master Plant Control System", "type": "scada_system", "tier": "Tier 1 Plant Safety", "provider": "On-Premises High Availability", "health": "healthy"},
            {"id": "CI-MFG-002", "name": "Siemens S7-1500 PLC Assembly Line Controller", "type": "plc_controller", "tier": "Tier 1 Robotic Assembly", "provider": "Industrial Fieldbus", "health": "healthy"},
            {"id": "CI-MFG-003", "name": "EMQX Industrial MQTT Sparkplug Broker", "type": "mqtt_broker", "tier": "Tier 1 Sensor Bus", "provider": "Edge Kubernetes Cluster", "health": "healthy"},
            {"id": "CI-MFG-004", "name": "TimescaleDB Industrial Historian", "type": "time_series_db", "tier": "Tier 2 Telemetry", "provider": "Local Plant Server", "health": "healthy"}
        ]
    },
    "telecom": {
        "id": "telecom",
        "name": "Telecommunications & 5G Carrier Operations",
        "icon": "📡",
        "sub_industries": [
            "Tier 1 Mobile Network Operator (5G/LTE)",
            "Fiber Internet Service Provider (FTTH)",
            "OTT Video Delivery & Transcoding Mesh",
            "Global Subsea Fiber & BGP Transit"
        ],
        "primary_offering": "5G Standalone (SA) Packet Core, VoLTE Calling & Ultra-Reliable Low-Latency Communication",
        "tech_stack": "5G gNodeB RAN, BGP Border Routers, OpenFlow SDN, Kafka, Diameter/SIP, Cassandra",
        "compliance_standard": "FCC E911 Reliability • 3GPP Release 17 • NEBS Level 3",
        "downtime_cost_per_minute": 21000.0,
        "layout_theme": "theme-telecom-noc",
        "badge_text": "📡 5G Carrier NOC Mode • E911 Priority",
        "sla_p1_resolve_hours": 0.5,
        "sla_p1_response_mins": 5,
        "taxonomies": {
            "5G RAN & Packet Core": {
                "5G gNodeB Cell Towers": ["Cell Site Carrier Signal Dropout", "Beamforming Antenna Failure", "Fronthaul Fiber Link Flap"],
                "5G SA Packet Core (UPF/AMF)": ["User Plane Function (UPF) Packet Drop", "AMF Subscriber Registration Spike"]
            },
            "IP Core & BGP Peering": {
                "BGP Border Routing & Peering": ["BGP Route Flapping / AS Path Poison", "DWDM Optical Transceiver Failure", "MPLS LSP Tunnel Desync"],
                "VoLTE & Voice Services": ["SIP Trunk Registration Timeout", "E911 Emergency Call Routing Alarm"]
            },
            "Customer Broadband & CPE": {
                "FTTH OLT Access Grid": ["GPON Splitter Signal Loss", "RADIUS AAA Authentication Timeout"]
            }
        },
        "cmdb_nodes": [
            {"id": "CI-TEL-001", "name": "5G SA User Plane Function (UPF Core)", "type": "packet_core", "tier": "Tier 1 Carrier Core", "provider": "Telco Cloud NFV", "health": "healthy"},
            {"id": "CI-TEL-002", "name": "Cisco 8000 BGP Core Edge Router", "type": "border_router", "tier": "Tier 1 Transit", "provider": "Primary Carrier POP", "health": "healthy"},
            {"id": "CI-TEL-003", "name": "IMS VoLTE Telephony Switch", "type": "voice_switch", "tier": "Tier 1 E911 Voice", "provider": "Nokia CloudBand", "health": "healthy"},
            {"id": "CI-TEL-004", "name": "GPON OLT Fiber Access Shelf (Metropolitan)", "type": "optical_olt", "tier": "Tier 2 Access", "provider": "Central Office 04", "health": "healthy"}
        ]
    }
}


# ============================================================================
# DATABASE SETUP & INITIALIZATION
# ============================================================================

def init_industry_tables():
    """Ensure company DNA profile table exists."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_company_dna (
                id INTEGER PRIMARY KEY,
                industry_id TEXT NOT NULL,
                industry_name TEXT NOT NULL,
                sub_industry TEXT NOT NULL,
                primary_offering TEXT,
                tech_stack TEXT,
                compliance_standard TEXT,
                downtime_cost_per_minute REAL DEFAULT 18500.0,
                layout_theme TEXT DEFAULT 'theme-fintech-sapphire',
                badge_text TEXT DEFAULT '🔒 PCI-DSS Level 1 Banking Mode',
                active_blueprint JSON,
                updated_at TEXT
            )
        """)
        # Seed default if empty (FinTech default)
        cursor.execute("SELECT COUNT(*) FROM config_company_dna")
        if cursor.fetchone()[0] == 0:
            fin = INDUSTRY_BLUEPRINTS["fintech"]
            now = datetime.datetime.utcnow().isoformat() + "Z"
            cursor.execute("""
                INSERT INTO config_company_dna (
                    id, industry_id, industry_name, sub_industry, primary_offering,
                    tech_stack, compliance_standard, downtime_cost_per_minute,
                    layout_theme, badge_text, active_blueprint, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fin["id"], fin["name"], fin["sub_industries"][0], fin["primary_offering"],
                fin["tech_stack"], fin["compliance_standard"], fin["downtime_cost_per_minute"],
                fin["layout_theme"], fin["badge_text"], json.dumps(fin), now
            ))
        conn.commit()


init_industry_tables()


# ============================================================================
# CORE BLUEPRINT METHODS
# ============================================================================

def get_current_dna_profile() -> Dict[str, Any]:
    """Retrieve active enterprise DNA configuration."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, industry_id, industry_name, sub_industry, primary_offering,
                   tech_stack, compliance_standard, downtime_cost_per_minute,
                   layout_theme, badge_text, active_blueprint, updated_at
            FROM config_company_dna WHERE id = 1
        """)
        row = cursor.fetchone()
        if not row:
            return INDUSTRY_BLUEPRINTS["fintech"]
        
        return {
            "id": row[0],
            "industry_id": row[1],
            "industry_name": row[2],
            "sub_industry": row[3],
            "primary_offering": row[4],
            "tech_stack": row[5],
            "compliance_standard": row[6],
            "downtime_cost_per_minute": row[7],
            "layout_theme": row[8],
            "badge_text": row[9],
            "active_blueprint": json.loads(row[10]) if row[10] else {},
            "updated_at": row[11]
        }


def apply_industry_blueprint(
    industry_id: str,
    sub_industry: Optional[str] = None,
    offering: Optional[str] = None,
    tech_stack: Optional[str] = None,
    downtime_cost: Optional[float] = None
) -> Dict[str, Any]:
    """
    Applies the industry blueprint to OpenNow.
    Persists DNA in database and syncs master data taxonomies.
    """
    if industry_id not in INDUSTRY_BLUEPRINTS:
        raise ValueError(f"Unknown industry ID '{industry_id}'. Supported: {list(INDUSTRY_BLUEPRINTS.keys())}")

    bp = INDUSTRY_BLUEPRINTS[industry_id]
    chosen_sub = sub_industry or bp["sub_industries"][0]
    chosen_offering = offering or bp["primary_offering"]
    chosen_tech = tech_stack or bp["tech_stack"]
    chosen_cost = downtime_cost if downtime_cost is not None else bp["downtime_cost_per_minute"]
    now = datetime.datetime.utcnow().isoformat() + "Z"

    # 1. Update config_company_dna table
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE config_company_dna
            SET industry_id = ?, industry_name = ?, sub_industry = ?,
                primary_offering = ?, tech_stack = ?, compliance_standard = ?,
                downtime_cost_per_minute = ?, layout_theme = ?, badge_text = ?,
                active_blueprint = ?, updated_at = ?
            WHERE id = 1
        """, (
            bp["id"], bp["name"], chosen_sub, chosen_offering,
            chosen_tech, bp["compliance_standard"], chosen_cost,
            bp["layout_theme"], bp["badge_text"], json.dumps(bp), now
        ))
        conn.commit()

    # 2. Sync dynamic taxonomies in config_engine tables if present
    try:
        from backend.config_engine import config_engine
        # Clear out existing runtime taxonomy and seed industry specific tree
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_items")
            cursor.execute("DELETE FROM config_subcategories")
            cursor.execute("DELETE FROM config_categories")
            
            for cat_name, subcats in bp["taxonomies"].items():
                cursor.execute("""
                    INSERT INTO config_categories (name, code, description, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?)
                """, (cat_name, cat_name[:6].upper(), f"{cat_name} in {bp['name']}", now, now))
                cat_id = cursor.lastrowid
                
                for sub_name, items in subcats.items():
                    cursor.execute("""
                        INSERT INTO config_subcategories (category_id, name, code, description, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, 1, ?, ?)
                    """, (cat_id, sub_name, sub_name[:6].upper(), f"{sub_name} under {cat_name}", now, now))
                    sub_id = cursor.lastrowid
                    
                    for item_name in items:
                        cursor.execute("""
                            INSERT INTO config_items (subcategory_id, name, code, description, is_active, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 1, ?, ?)
                        """, (sub_id, item_name, item_name[:6].upper(), f"{item_name} component", now, now))
            conn.commit()
    except Exception as exc:
        logger.warning(f"Could not automatically sync config_engine tables: {exc}")

    logger.info(f"Successfully applied industry blueprint: {bp['name']} ({chosen_sub})")
    return get_current_dna_profile()


# ============================================================================
# PYDANTIC SCHEMAS FOR API
# ============================================================================

class ApplyBlueprintRequest(BaseModel):
    industry_id: str = Field(..., description="Industry ID: fintech, healthcare, retail, saas_ai, manufacturing, telecom")
    sub_industry: Optional[str] = None
    primary_offering: Optional[str] = None
    tech_stack: Optional[str] = None
    downtime_cost_per_minute: Optional[float] = None


# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@industry_router.get("/blueprints")
def list_industry_blueprints():
    """List all available enterprise industry blueprints."""
    return {
        "status": "success",
        "total": len(INDUSTRY_BLUEPRINTS),
        "blueprints": list(INDUSTRY_BLUEPRINTS.values())
    }


@industry_router.get("/current")
def get_active_dna():
    """Get currently active company DNA and industry settings."""
    profile = get_current_dna_profile()
    return {
        "status": "success",
        "dna": profile
    }


@industry_router.post("/apply", status_code=status.HTTP_200_OK)
def apply_blueprint_endpoint(req: ApplyBlueprintRequest):
    """Apply an industry blueprint and adapt all OpenNow master data & layouts."""
    try:
        updated = apply_industry_blueprint(
            industry_id=req.industry_id,
            sub_industry=req.sub_industry,
            offering=req.primary_offering,
            tech_stack=req.tech_stack,
            downtime_cost=req.downtime_cost_per_minute
        )
        return {
            "status": "success",
            "message": f"Successfully tailored OpenNow to {updated['industry_name']} ({updated['sub_industry']})",
            "dna": updated
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying industry blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to apply blueprint: {str(e)}")


# ============================================================================
# SELF-TEST SUITE
# ============================================================================

if __name__ == "__main__":
    import unittest

    class TestIndustryEngine(unittest.TestCase):
        def test_01_catalog_completeness(self):
            self.assertEqual(len(INDUSTRY_BLUEPRINTS), 6)
            self.assertIn("fintech", INDUSTRY_BLUEPRINTS)
            self.assertIn("healthcare", INDUSTRY_BLUEPRINTS)
            self.assertIn("retail", INDUSTRY_BLUEPRINTS)
            self.assertIn("saas_ai", INDUSTRY_BLUEPRINTS)
            self.assertIn("manufacturing", INDUSTRY_BLUEPRINTS)
            self.assertIn("telecom", INDUSTRY_BLUEPRINTS)

        def test_02_get_current_dna(self):
            dna = get_current_dna_profile()
            self.assertIsNotNone(dna)
            self.assertIn("industry_id", dna)

        def test_03_apply_healthcare_blueprint(self):
            updated = apply_industry_blueprint("healthcare", "Hospital EHR/EMR Clinical Operations")
            self.assertEqual(updated["industry_id"], "healthcare")
            self.assertEqual(updated["sub_industry"], "Hospital EHR/EMR Clinical Operations")
            self.assertEqual(updated["compliance_standard"], "HIPAA • HITECH • FDA 21 CFR Part 11 • Joint Commission")

        def test_04_apply_saas_ai_blueprint(self):
            updated = apply_industry_blueprint("saas_ai", "Autonomous AI & LLM Cloud Infrastructure")
            self.assertEqual(updated["industry_id"], "saas_ai")
            self.assertIn("NVIDIA", updated["tech_stack"])

        def test_05_reapply_fintech(self):
            updated = apply_industry_blueprint("fintech")
            self.assertEqual(updated["industry_id"], "fintech")
            self.assertIn("PCI-DSS", updated["compliance_standard"])

    suite = unittest.TestLoader().loadTestsFromTestCase(TestIndustryEngine)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    if not res.wasSuccessful():
        sys.exit(1)
    print("ALL INDUSTRY ENGINE TESTS PASSED!")
