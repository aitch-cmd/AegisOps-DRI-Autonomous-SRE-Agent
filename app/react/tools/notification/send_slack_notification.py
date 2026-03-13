"""
Notification Tool — send_slack_notification
Post incident update or resolution summary to configured Slack channel.
"""

import os

import httpx
from langchain_core.tools import tool

from app.core.logging import get_logger

logger = get_logger(__name__)

_SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

@tool
async def send_slack_notification(
    channel: str,
    message: str,
    severity: str = "info",
) -> dict:
    """
    Post an incident update or resolution summary to a Slack channel.

    Args:
        channel:  Slack channel name (e.g. '#notification').
        message:  Markdown-formatted message body.
        severity: Label to attach — critical | high | medium | low | info.

    Returns:
        Dict with success flag and any error.
    """
    if not _SLACK_BOT_TOKEN:
        return {"success": False, "error": "SLACK_BOT_TOKEN environment variable is not set."}

    color_map = {
        "critical": "#FF0000",
        "high": "#FF6600",
        "medium": "#FFCC00",
        "low": "#36A64F",
        "info": "#439FE0",
    }

    payload = {
        "channel": channel,
        "attachments": [
            {
                "color": color_map.get(severity, "#439FE0"),
                "text": message,
                "footer": "AegisOps Agent",
            }
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
                logger.error(f"Slack notification failed: {error_msg}")
                return {"success": False, "error": error_msg}
                
        return {"success": True, "error": None}
    except Exception as e:
        logger.error(f"Slack notification failed: {e}")
        return {"success": False, "error": str(e)}
