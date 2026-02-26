"""
Notification Tool — send_approval_request
Post L3 action approval request with [Approve]/[Deny] buttons to Slack.
"""

import os

import httpx
from langchain_core.tools import tool

from app.core.logging import get_logger

logger = get_logger(__name__)

_SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


@tool
async def send_approval_request(
    channel: str,
    action: str,
    service: str,
    details: str,
    incident_id: str,
) -> dict:
    """
    Post an L3 action approval request with Approve / Deny buttons to Slack.

    Args:
        channel:     Slack channel name (e.g. '#incident-approvals').
        action:      Action awaiting approval (e.g. 'scale_service').
        service:     Target service name.
        details:     Human-readable summary of what will happen.
        incident_id: Incident identifier for callback correlation.

    Returns:
        Dict with success flag and any error.
    """
    payload = {
        "channel": channel,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"🔐 *Approval Required*\n"
                        f"*Action:* `{action}`\n"
                        f"*Service:* `{service}`\n"
                        f"*Details:* {details}\n"
                        f"*Incident:* `{incident_id}`"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "style": "primary",
                        "value": f"approve:{incident_id}:{action}",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Deny"},
                        "style": "danger",
                        "value": f"deny:{incident_id}:{action}",
                    },
                ],
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=5) as http:
            resp = await http.post(_SLACK_WEBHOOK_URL, json=payload)
            resp.raise_for_status()
        return {"success": True, "error": None}
    except Exception as e:
        logger.error(f"Approval request failed: {e}")
        return {"success": False, "error": str(e)}
