"""
AegisOps Tool Registry
All tools available to the ReAct agent during reasoning.
"""

# ── Diagnostic ─────────────────────────────────────────────────────────────
from app.react.tools.diagnostic.get_logs import get_logs
from app.react.tools.diagnostic.get_pod_status import get_pod_status

# ── Memory (mid-reasoning) ────────────────────────────────────────────────
from app.react.tools.memory.retrieve_runbook import retrieve_runbook

# ── Action (policy-gated) ─────────────────────────────────────────────────
from app.react.tools.action.restart_deployment import restart_deployment

# ── Verification ───────────────────────────────────────────────────────────
from app.react.tools.verification.check_service_health import check_service_health

# ── Notification ───────────────────────────────────────────────────────────
from app.react.tools.notification.write_audit_log import write_audit_log

# NOTE: retrieve_similar_incidents → pre-loaded in memory_node (not a mid-reasoning tool)
# NOTE: save_incident_memory       → called in resolution_node (not a mid-reasoning tool)

ALL_TOOLS = [
    # Diagnostic
    get_pod_status,
    get_logs,
    
    # Memory
    retrieve_runbook,
    
    # Action
    restart_deployment,
    
    # Verification
    check_service_health,
    
    # Notification
    write_audit_log,
]
