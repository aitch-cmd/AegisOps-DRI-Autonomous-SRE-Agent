"""
AegisOps Tool Registry
All tools available to the ReAct agent during reasoning.
"""

# ── Diagnostic ─────────────────────────────────────────────────────────────
from app.react.tools.diagnostic.get_metrics import get_metrics
from app.react.tools.diagnostic.get_logs import get_logs
from app.react.tools.diagnostic.get_error_traces import get_error_traces
from app.react.tools.diagnostic.get_pod_status import get_pod_status

# ── Memory (mid-reasoning) ────────────────────────────────────────────────
from app.react.tools.memory.retrieve_runbook import retrieve_runbook
from app.react.tools.memory.retrieve_policy import retrieve_policy

# ── Action (policy-gated) ─────────────────────────────────────────────────
from app.react.tools.action.restart_deployment import restart_deployment
from app.react.tools.action.rollback_release import rollback_release
from app.react.tools.action.scale_service import scale_service
from app.react.tools.action.toggle_feature_flag import toggle_feature_flag
from app.react.tools.action.update_configmap import update_config_map

# ── Verification ───────────────────────────────────────────────────────────
from app.react.tools.verification.check_service_health import check_service_health
from app.react.tools.verification.compare_metrics_before_after import compare_metrics_before_after
from app.react.tools.verification.verify_rollout_status import verify_rollout_status

# ── Notification ───────────────────────────────────────────────────────────
from app.react.tools.notification.send_slack_notification import send_slack_notification
from app.react.tools.notification.send_approval_request import send_approval_request
from app.react.tools.notification.escalate_to_human import escalate_to_human
from app.react.tools.notification.write_audit_log import write_audit_log

# NOTE: retrieve_similar_incidents → pre-loaded in memory_node (not a mid-reasoning tool)
# NOTE: save_incident_memory       → called in resolution_node (not a mid-reasoning tool)

ALL_TOOLS = [
    # Diagnostic
    get_metrics,
    get_logs,
    get_error_traces,
    get_pod_status,
    # Memory
    retrieve_runbook,
    retrieve_policy,
    # Action
    restart_deployment,
    rollback_release,
    scale_service,
    toggle_feature_flag,
    update_config_map,
    # Verification
    check_service_health,
    compare_metrics_before_after,
    verify_rollout_status,
    # Notification
    send_slack_notification,
    send_approval_request,
    escalate_to_human,
    write_audit_log,
]
