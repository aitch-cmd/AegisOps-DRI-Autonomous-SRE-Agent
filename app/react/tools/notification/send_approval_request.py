"""
Notification Tool — send_approval_request
Post L3 action approval request with [Approve]/[Deny] buttons to Slack.
"""

import os

import httpx
from langchain_core.tools import tool

from app.core.logging import get_logger

logger = get_logger(__name__)

_SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

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
        channel:     Slack channel name (e.g. '#approvals').
        action:      Action awaiting approval (e.g. 'scale_service').
        service:     Target service name.
        details:     Human-readable summary of what will happen.
        incident_id: Incident identifier for callback correlation.

    Returns:
        Dict with success flag and any error.
    """
    if not _SLACK_BOT_TOKEN:
        return {"success": False, "error": "SLACK_BOT_TOKEN environment variable is not set."}

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
    
    headers = {
        "Authorization": f"Bearer {_SLACK_BOT_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    }

    try:
        async with httpx.AsyncClient(timeout=5) as http:
            resp = await http.post(
                "https://slack.com/api/chat.postMessage",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                error_msg = data.get("error", "Unknown Slack API error")
                logger.error(f"Approval request failed: {error_msg}")
                return {"success": False, "error": error_msg}
                
        return {"success": True, "error": None}
    except Exception as e:
        logger.error(f"Approval request failed: {e}")
        return {"success": False, "error": str(e)}
