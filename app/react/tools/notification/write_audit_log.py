import json
from datetime import datetime, timezone

from langchain_core.tools import tool

from app.core.logging import get_logger

logger = get_logger(__name__)


@tool
def write_audit_log(
    incident_id: str,
    tool_name: str,
    params: dict,
    result: dict,
    policy_decision: dict,
    success: bool,
) -> str:
    """
    Append a tool call record to the permanent audit trail.

    Args:
        incident_id:     Incident this action belongs to.
        tool_name:       Name of the tool that was invoked.
        params:          Parameters passed to the tool.
        result:          Result returned by the tool.
        policy_decision: PolicyDecision dict (action, allowed, reason …).
        success:         Whether the tool call succeeded.

    Returns:
        Confirmation string.
    """
    entry = {
        "type": "audit",
        "incident_id": incident_id,
        "tool_name": tool_name,
        "params": params,
        "result": result,
        "policy_decision": policy_decision,
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("AUDIT_LOG %s", json.dumps(entry, default=str))

    return f"audit_log written: {tool_name} for incident {incident_id}"
