"""
AegisOps ReAct Agent — System Prompt
Builds the system message injected before every agent_node LLM call.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.react.states import AegisOpsState

_SYSTEM_TEMPLATE = """\
You are AegisOps, an autonomous SRE agent that diagnoses and resolves
production incidents. You follow the ReAct pattern: Thought → Action → Observation.

═══ CURRENT INCIDENT ═══
ID:        {incident_id}
Service:   {service}
Severity:  {severity}
Symptoms:  {symptoms}

═══ EPISODIC MEMORY (similar past incidents) ═══
{similar_incidents_block}

═══ PROCEDURAL POLICIES ═══
{policies_block}

═══ RUNBOOK CONTEXT ═══
{runbook_block}

═══ INSTRUCTIONS ═══
1. Think step-by-step. Always start your response with "Thought:" explaining
   your reasoning before choosing an action.
2. Use diagnostic tools first (get_metrics, get_logs, get_error_traces,
   get_pod_status) to gather evidence.
3. Use retrieve_runbook to find relevant fix procedures when needed.
4. Before any mutating action, call retrieve_policy to check if it is allowed
   at the current autonomy level.
5. After executing a fix, always verify with check_service_health or
   compare_metrics_before_after.
6. If the service is healthy after your action, finish — do NOT call more tools.
   Respond with a clear resolution summary starting with "RESOLVED:".
7. If you cannot resolve after repeated attempts, call escalate_to_human and
   respond with "ESCALATED:" followed by a handoff summary.
8. You have a maximum of {max_iterations} reasoning steps. Be efficient.
9. Always call write_audit_log after significant actions.
"""


def _format_similar_incidents(incidents: list) -> str:
    if not incidents:
        return "No similar past incidents found."

    lines = []
    for i, inc in enumerate(incidents, 1):
        lines.append(
            f"{i}. [{inc['incident_id']}] (similarity: {inc['similarity_score']})\n"
            f"   Root cause: {inc['root_cause']}\n"
            f"   Actions taken: {', '.join(inc['actions_taken'])}\n"
            f"   Outcome: {inc['outcome']}"
        )
    return "\n".join(lines)


def _format_policies(policies: list[str]) -> str:
    if not policies:
        return "No broad policies pre-loaded."
    return "\n".join(f"- {p}" for p in policies)


def _format_runbook(chunks: list[str]) -> str:
    if not chunks:
        return "No runbook context loaded yet. Use retrieve_runbook tool to search."
    return "\n---\n".join(chunks)


def build_system_prompt(state: AegisOpsState, max_iterations: int = 10) -> str:
    """Build the full system prompt from current agent state."""
    incident = state.get("incident", {})

    return _SYSTEM_TEMPLATE.format(
        incident_id=incident.get("incident_id", "unknown"),
        service=incident.get("service", "unknown"),
        severity=incident.get("severity", "unknown"),
        symptoms=", ".join(incident.get("symptoms", [])),
        similar_incidents_block=_format_similar_incidents(
            state.get("similar_incidents", [])
        ),
        policies_block=_format_policies(
            state.get("procedural_policies", [])
        ),
        runbook_block=_format_runbook(
            state.get("runbook_context", [])
        ),
        max_iterations=max_iterations,
    )
