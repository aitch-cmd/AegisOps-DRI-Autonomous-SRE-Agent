import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parents[1]))

from sqlalchemy import delete
from app.database import get_db_session
from app.models.policies import Policy
from app.models.knowledge_base import KnowledgeBase
from app.models.incident_memory import IncidentMemory
from app.core.embedding import _embedder

async def seed_policies():
    print("Seeding policies...")
    policies = [
        # Global Wildcards
        Policy(
            action="restart_deployment",
            service="*",
            severity="*",
            min_autonomy_level="L2",
            requires_approval=False,
            reason="Standard rolling restart is allowed automatically at L2."
        ),
        Policy(
            action="get_logs",
            service="*",
            severity="*",
            min_autonomy_level="L1",
            requires_approval=False,
            reason="Read-only diagnostic actions allowed at L1."
        ),
        # Service Specific
        Policy(
            action="scale_service",
            service="payment-service",
            severity="critical",
            min_autonomy_level="L3",
            requires_approval=True,
            reason="Scaling payment-service during critical incidents requires human approval."
        ),
        Policy(
            action="toggle_feature_flag",
            service="auth-service",
            severity="*",
            min_autonomy_level="L2",
            requires_approval=False,
            reason="Auth service flag toggles allowed at L2 if policies met."
        ),
    ]
    
    async with get_db_session() as db:
        await db.execute(delete(Policy))  # Clear existing
        db.add_all(policies)
        await db.commit()

async def seed_knowledge():
    print("Seeding knowledge base (runbooks)...")
    kb_items = [
        {
            "category": "runbooks",
            "doc_name": "OOMKill_Triage.md",
            "text": "Symptom: Pod restarts with OOMKill. Action: 1. Run get_pod_status to verify restart counts. 2. Fetch logs via get_logs for 'OutOfMemoryError'. 3. If traffic is high, use scale_deployment to add replicas. 4. If a recent change occurred, use update_deployment_image to rollback to a stable version."
        },
        {
            "category": "runbooks",
            "doc_name": "High_Latency_Triaging.md",
            "text": "Symptom: P99 latency > 2s or High Error Rate. Action: 1. Use check_service_health to verify Prometheus metrics. 2. Use get_logs to look for timeout patterns. 3. Use scale_deployment to handle load spikes. 4. If pods are stuck, use restart_deployment to clear state."
        },
        {
            "category": "architecture",
            "doc_name": "Service_Topology.md",
            "text": "The test-app (Nginx) is the primary entry point in the Kind cluster. It uses standard labels 'app=test-app' for discovery by the AegisOps tools."
        }
    ]
    
    async with get_db_session() as db:
        await db.execute(delete(KnowledgeBase))
        for item in kb_items:
            embedding = await _embedder.aembed_query(item["text"])
            db.add(KnowledgeBase(
                category=item["category"],
                doc_name=item["doc_name"],
                chunk_text=item["text"],
                embedding=embedding
            ))
        await db.commit()

async def seed_incidents():
    print("Seeding incident memory (episodic)...")
    incidents = [
        {
            "incident_id": "INC-ALPHA",
            "symptoms": ["High Error Rate", "Service timeouts"],
            "root_cause": "Traffic spike overwhelmed pod capacity.",
            "actions_taken": ["get_pod_status", "scale_deployment", "check_service_health"],
            "outcome": "Resolved",
            "mttr_seconds": 300
        },
        {
            "incident_id": "INC-BETA",
            "symptoms": ["Internal Server Error", "Process hang"],
            "root_cause": "Application deadlock in worker thread.",
            "actions_taken": ["get_logs", "restart_deployment", "check_service_health"],
            "outcome": "Resolved",
            "mttr_seconds": 600
        }
    ]
    
    async with get_db_session() as db:
        await db.execute(delete(IncidentMemory))
        for item in incidents:
            embed_text = " ".join(item["symptoms"]) + " " + item["root_cause"]
            embedding = await _embedder.aembed_query(embed_text)
            db.add(IncidentMemory(
                incident_id=item["incident_id"],
                symptoms=item["symptoms"],
                root_cause=item["root_cause"],
                actions_taken=item["actions_taken"],
                outcome=item["outcome"],
                mttr_seconds=item["mttr_seconds"],
                embedding=embedding
            ))
        await db.commit()

async def main():
    try:
        await seed_policies()
        await seed_knowledge()
        await seed_incidents()
        print("Done seeding AegisOps data!")
    except Exception as e:
        print(f"Error seeding data: {e}")

if __name__ == "__main__":
    asyncio.run(main())
