"""
Slack Router
Handles inbound Slack Event Subscriptions and Interactive Component callbacks.

Endpoints:
  POST /slack/events  — URL verification challenge + event dispatch
  POST /slack/actions — Approve/Deny button callbacks
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.approval_store import resolve_approval
from app.core.logging import get_logger
from app.core.slack_verifier import verify_slack_signature
from app.react.graph import run_agent
from app.react.states import IncidentEvent

logger = get_logger(__name__)

router = APIRouter(prefix="/slack", tags=["Slack"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_mention_text(text: str) -> dict:
    """
    Parse a simple structured app-mention into incident fields.

    Expected format (case-insensitive):
        @AegisOps service: <name> severity: <level> symptoms: <comma list>

    Falls back to sensible defaults so the agent can still run.
    """
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    service_match = re.search(r"service[:\s]+([^\s,]+)", text, re.IGNORECASE)
    severity_match = re.search(r"severity[:\s]+(critical|high|medium|low)", text, re.IGNORECASE)
    symptoms_match = re.search(r"symptoms[:\s]+(.+)", text, re.IGNORECASE)

    service = service_match.group(1) if service_match else "unknown"
    severity = severity_match.group(1).lower() if severity_match else "high"
    symptoms_raw = symptoms_match.group(1) if symptoms_match else text
    symptoms = [s.strip() for s in symptoms_raw.split(",") if s.strip()]

    return {
        "service": service,
        "severity": severity,
        "symptoms": symptoms or [text],
    }


async def _dispatch_agent(incident: IncidentEvent) -> None:
    """Run the agent graph; catch and log any errors."""
    try:
        result = await run_agent(incident)
        logger.info(
            "Slack-triggered incident %s resolved. Status: %s",
            incident["incident_id"],
            result.get("incident_status"),
        )
    except Exception as exc:
        logger.error("Agent failed for incident %s: %s", incident["incident_id"], exc)


# ── /slack/events ──────────────────────────────────────────────────────────

@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Receive Slack Event Subscriptions (Event API v2).

    Handles:
    - url_verification  — respond with challenge value (required by Slack)
    - app_mention       — parse the message and dispatch the ReAct agent
    """
    body = await request.body()
    payload = json.loads(body)

    # ── 1. URL verification challenge ─────────────────────────────────────
    # Slack sends this when you first configure the Request URL.
    # Signature check is intentionally skipped here — Slack does not sign
    # the challenge request with a final secret yet.
    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge", "")
        logger.info("Slack URL verification challenge received")
        return JSONResponse(content={"challenge": challenge})

    # ── 2. Signature verification for all real events ─────────────────────
    try:
        await verify_slack_signature(request)
    except HTTPException:
        # Re-raise so FastAPI returns appropriate 403
        raise

    event_type = payload.get("type")

    # ── 3. app_mention → trigger agent ────────────────────────────────────
    if event_type == "event_callback":
        event = payload.get("event", {})

        if event.get("type") == "app_mention":
            text = event.get("text", "")
            channel = event.get("channel", "")
            slack_user = event.get("user", "slack_user")

            parsed = _parse_mention_text(text)
            incident_id = str(uuid.uuid4())

            incident: IncidentEvent = {
                "incident_id": incident_id,
                "source": "slack",
                "severity": parsed["severity"],
                "service": parsed["service"],
                "symptoms": parsed["symptoms"],
                "raw_payload": {
                    "slack_channel": channel,
                    "slack_user": slack_user,
                    "original_text": text,
                },
                "received_at": datetime.now(timezone.utc).isoformat(),
                # Extra fields consumed by run_agent
                "autonomy_level": "L2",
                "user_id": slack_user,
                "session_id": incident_id,
            }

            background_tasks.add_task(_dispatch_agent, incident)
            logger.info(
                "app_mention from %s: dispatching agent for incident %s (service=%s, severity=%s)",
                slack_user, incident_id, parsed["service"], parsed["severity"],
            )
            return JSONResponse(content={"status": "accepted", "incident_id": incident_id})

    # ── 4. Any other event — acknowledge ──────────────────────────────────
    return JSONResponse(content={"status": "ok"})


# ── /slack/actions ─────────────────────────────────────────────────────────

@router.post("/actions")
async def slack_actions(request: Request):
    """
    Receive Slack Interactive Component callbacks (button clicks).

    Handles Approve / Deny buttons posted by send_approval_request tool.
    Button value format: `approve:{incident_id}:{action}` or `deny:{incident_id}:{action}`
    """
    # Verify signature
    await verify_slack_signature(request)

    # Slack sends actions as form-encoded  payload=<url-encoded JSON>
    form = await request.form()
    raw_payload = form.get("payload", "")

    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid payload format")

    actions = payload.get("actions", [])
    if not actions:
        return JSONResponse(content={"status": "ok", "message": "No actions found"})

    action_value: str = actions[0].get("value", "")

    # Parse  approve:{incident_id}:{action_name}  or  deny:{incident_id}:{action_name}
    parts = action_value.split(":", 2)
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail=f"Unrecognised action value: {action_value!r}")

    decision_str, incident_id = parts[0], parts[1]
    action_name = parts[2] if len(parts) > 2 else "unknown"

    if decision_str not in ("approve", "deny"):
        raise HTTPException(status_code=400, detail=f"Unknown decision: {decision_str!r}")

    decision = "approved" if decision_str == "approve" else "denied"
    resolved = resolve_approval(incident_id, decision)  # type: ignore[arg-type]

    operator = payload.get("user", {}).get("name", "unknown")
    logger.info(
        "Slack action: incident=%s decision=%s action=%s operator=%s resolved=%s",
        incident_id, decision, action_name, operator, resolved,
    )

    # Return a Slack response that replaces the button message
    emoji = "✅" if decision == "approved" else "❌"
    response_text = (
        f"{emoji} *{decision.capitalize()}* by `{operator}`\n"
        f"Action `{action_name}` for incident `{incident_id}` has been {decision}."
    )

    return JSONResponse(content={
        "response_type": "in_channel",
        "replace_original": True,
        "text": response_text,
        "status": "ok",
        "decision": decision,
    })
