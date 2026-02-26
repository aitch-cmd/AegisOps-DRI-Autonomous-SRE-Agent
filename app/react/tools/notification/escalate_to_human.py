"""
Notification Tool — escalate_to_human
Page on-call engineer via PagerDuty if the agent cannot resolve.
"""

import os

import httpx
from langchain_core.tools import tool

from app.core.logging import get_logger

logger = get_logger(__name__)

_PD_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"
_PD_ROUTING_KEY = os.environ.get("PAGERDUTY_ROUTING_KEY", "")


@tool
async def escalate_to_human(
    service: str,
    incident_id: str,
    summary: str,
    severity: str = "high",
) -> dict:
    """
    Page on-call engineer via PagerDuty Events API v2.

    Args:
        service:     Logical service name.
        incident_id: Incident identifier for dedup.
        summary:     Human-readable description of the problem.
        severity:    PagerDuty severity — critical | error | warning | info.

    Returns:
        Dict with success flag and any error.
    """
    payload = {
        "routing_key": _PD_ROUTING_KEY,
        "event_action": "trigger",
        "dedup_key": incident_id,
        "payload": {
            "summary": f"[AegisOps] {service}: {summary}",
            "severity": severity,
            "source": "aegisops-agent",
            "component": service,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=5) as http:
            resp = await http.post(_PD_EVENTS_URL, json=payload)
            resp.raise_for_status()
        return {"success": True, "error": None}
    except Exception as e:
        logger.error(f"PagerDuty escalation failed: {e}")
        return {"success": False, "error": str(e)}
