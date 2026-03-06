"""
AegisOps ReAct Agent — LangGraph StateGraph
Wires: START → memory_node → agent_node ←→ tools (loop) → resolution_node → END
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage

from app.react.states import AegisOpsState, IncidentEvent
from app.react.nodes import memory_node, agent_node, resolution_node
from app.react.tools import ALL_TOOLS

from app.utils.load_params import load_params

params = load_params("app/params.yml")
_MAX_ITERATIONS = params.get("agent", {}).get("max_iterations", 10)


# ── Routing logic ──────────────────────────────────────────────────────────

def _should_continue(state: AegisOpsState) -> str:
    """Route after agent_node: tools, resolution, or forced-end."""

    # Guard: max iterations reached → force resolution
    if state.get("iteration", 0) >= _MAX_ITERATIONS:
        return "resolution_node"

    last_msg = state["messages"][-1]

    # If the LLM made tool calls, route to tools
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"

    # If content contains RESOLVED or ESCALATED, go to resolution
    content = getattr(last_msg, "content", "") or ""
    if "RESOLVED:" in content or "ESCALATED:" in content:
        return "resolution_node"

    # Default: done reasoning, resolve
    return "resolution_node"


# ── Build graph ────────────────────────────────────────────────────────────

def build_graph():
    """Construct and return the AegisOps ReAct agent graph builder."""

    tools_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(AegisOpsState)

    # Add nodes
    graph.add_node("memory_node", memory_node)
    graph.add_node("agent_node", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("resolution_node", resolution_node)

    # Edges
    graph.add_edge(START, "memory_node")
    graph.add_edge("memory_node", "agent_node")
    graph.add_conditional_edges(
        "agent_node",
        _should_continue,
        {
            "tools": "tools",
            "resolution_node": "resolution_node",
        },
    )
    graph.add_edge("tools", "agent_node")
    graph.add_edge("resolution_node", END)

    return graph


# Graph builder singleton
graph_builder = build_graph()


# ── Entry point ────────────────────────────────────────────────────────────

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.settings import settings

async def run_agent(incident: IncidentEvent) -> dict:
    """
    Run the ReAct agent for a given incident event.

    Args:
        incident: IncidentEvent dict with incident_id, service, severity, etc.

    Returns:
        Final agent state dict after resolution.
    """
    initial_state = {
        "messages": [
            HumanMessage(content=(
                f"New incident alert:\n"
                f"ID: {incident['incident_id']}\n"
                f"Service: {incident['service']}\n"
                f"Severity: {incident['severity']}\n"
                f"Symptoms: {', '.join(incident['symptoms'])}\n"
                f"Please diagnose and resolve this incident."
            ))
        ],
        "incident": incident,
        "incident_status": "investigating",
        "similar_incidents": [],
        "runbook_context": [],
        "procedural_policies": [],
        "current_thought": "",
        "iteration": 0,
        "diagnosis": None,
        "pending_action": None,
        "policy_decision": None,
        "approval_status": None,
        "tool_invocations": [],
        "expected_outcome": None,
        "health_check": None,
        "verification_passed": None,
        "retry_count": 0,
        "resolution_summary": None,
        "mttr_seconds": None,
        "slack_notified": False,
        "autonomy_level": incident.get("autonomy_level", "L2"),
        "user_id": incident.get("user_id", "system"),
        "session_id": incident.get("session_id", incident["incident_id"]),
        "error": None,
    }

    # Format SQLAlchemy async URL driver to psycopg standard driver for langgraph-checkpoint-postgres
    # e.g. postgresql+asyncpg://... -> postgresql://...
    db_uri = settings.DATABASE_URL
    if db_uri.startswith("postgresql+asyncpg://"):
        db_uri = db_uri.replace("postgresql+asyncpg://", "postgresql://", 1)
        
    async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
        # Compile graph dynamically with the active checkpointer
        app = graph_builder.compile(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": incident["incident_id"]}}
        
        result = await app.ainvoke(initial_state, config=config)
        return result
