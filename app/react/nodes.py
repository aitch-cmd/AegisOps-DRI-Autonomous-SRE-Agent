"""
AegisOps ReAct Agent — Graph Nodes
memory_node  → pre-loads episodic + procedural context
agent_node   → LLM ReAct reasoning step
resolution_node → persist outcome + notify
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from langchain_core.messages import SystemMessage

from app.core.llm import llm
from app.react.prompt import build_system_prompt
from app.react.states import AegisOpsState
from app.react.tools import ALL_TOOLS
from app.react.tools.memory.retrieve_similar_incidents import retrieve_similar_incidents
from app.react.tools.memory.save_incident_memory import save_incident_memory
from app.react.tools.notification.send_slack_notification import send_slack_notification

from sqlalchemy import select
from app.database import get_db_session
from app.models.policies import Policy

from app.utils.load_params import load_params

params = load_params("app/params.yml")
_MAX_ITERATIONS = params.get("agent", {}).get("max_iterations", 10)


# ── memory_node ────────────────────────────────────────────────────────────

async def memory_node(state: AegisOpsState) -> dict:
    """Pre-load episodic memory and procedural policies before reasoning."""

    incident = state["incident"]

    # Episodic: retrieve similar past incidents via pgvector (Disabled for Portfolio Demo)
    # similar = await retrieve_similar_incidents.ainvoke(
    #     {"symptoms": incident["symptoms"]}
    # )
    similar = []

    # Procedural: load broad policies for this service
    service = incident["service"]
    async with get_db_session() as db:
        stmt = select(Policy).where(
            (Policy.service == service) | (Policy.service == "*")
        )
        rows = (await db.execute(stmt)).scalars().all()

    policies = [
        f"[{p.action}] service={p.service} severity={p.severity} "
        f"min_level={p.min_autonomy_level} approval={p.requires_approval} — {p.reason}"
        for p in rows
    ]

    return {
        "similar_incidents": similar,
        "procedural_policies": policies,
        "incident_status": "investigating",
    }


# ── agent_node ─────────────────────────────────────────────────────────────

_llm_with_tools = llm.bind_tools(ALL_TOOLS)


async def agent_node(state: AegisOpsState) -> dict:
    """Single ReAct reasoning step: Thought → Action (or final answer)."""

    system_prompt = build_system_prompt(state, max_iterations=_MAX_ITERATIONS)
    system_msg = SystemMessage(content=system_prompt)

    # Prepend system message, then pass full conversation
    messages = [system_msg] + state["messages"]

    response = await _llm_with_tools.ainvoke(messages)

    iteration = state.get("iteration", 0) + 1

    return {
        "messages": [response],
        "iteration": iteration,
    }


# ── resolution_node ────────────────────────────────────────────────────────

async def resolution_node(state: AegisOpsState) -> dict:
    """Persist resolved incident to pgvector and notify via Slack."""

    incident = state["incident"]

    # Calculate MTTR
    received_at = datetime.fromisoformat(incident["received_at"])
    mttr = int((datetime.now(timezone.utc) - received_at).total_seconds())

    # Extract resolution summary from last AI message
    last_msg = state["messages"][-1]
    summary = getattr(last_msg, "content", "Incident resolved by AegisOps agent.")

    # Persist to episodic memory for future RAG (Disabled for Portfolio Demo)
    diagnosis = state.get("diagnosis") or {
        "root_cause_hypothesis": summary,
        "confidence_score": 0.0,
        "supporting_evidence": [],
        "recommended_actions": [],
    }

    # await save_incident_memory.ainvoke({
    #     "incident_id": incident["incident_id"],
    #     "symptoms": incident["symptoms"],
    #     "diagnosis": diagnosis,
    #     "tool_invocations": state.get("tool_invocations", []),
    #     "outcome": "resolved",
    #     "mttr_seconds": mttr,
    # })

    # Slack notification
    await send_slack_notification.ainvoke({
        "channel": "#notification",
        "message": (
            f"✅ *Incident Resolved*\n"
            f"*ID:* `{incident['incident_id']}`\n"
            f"*Service:* `{incident['service']}`\n"
            f"*MTTR:* {mttr}s\n"
            f"*Summary:* {summary[:500]}"
        ),
        "severity": incident["severity"],
    })

    return {
        "incident_status": "resolved",
        "resolution_summary": summary,
        "mttr_seconds": mttr,
        "slack_notified": True,
    }
