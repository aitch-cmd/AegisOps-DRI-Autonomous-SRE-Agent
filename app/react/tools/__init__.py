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
from app.react.tools.action.scale_deployment import scale_deployment
from app.react.tools.action.update_deployment_image import update_deployment_image

# ── Verification ───────────────────────────────────────────────────────────
from app.react.tools.verification.check_service_health import check_service_health

# ── Notification ───────────────────────────────────────────────────────────
from app.react.tools.notification.write_audit_log import write_audit_log
from app.react.tools.notification.send_slack_notification import send_slack_notification

# NOTE: save_incident_memory       → called in resolution_node (not a mid-reasoning tool)
from app.react.tools.memory.retrieve_similar_incidents import retrieve_similar_incidents
from app.react.tools.memory.retrieve_policy import retrieve_policy


ALL_TOOLS = [
    # Diagnostic
    get_pod_status,
    get_logs,
    
    # Memory
    retrieve_runbook,
    retrieve_similar_incidents,
    
    # Action
    restart_deployment,
    scale_deployment,
    update_deployment_image,
    
    # Verification
    check_service_health,
    
    # Notification
    write_audit_log,
    send_slack_notification,
    
    # Policy
    retrieve_policy,
]
