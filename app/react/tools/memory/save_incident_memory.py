"""
Episodic Memory Write Tool
Write a resolved incident back to IncidentMemory (pgvector) so future
incidents can retrieve it as episodic context.
"""

from datetime import datetime, timezone

from langchain_core.tools import tool
from sqlalchemy.dialects.postgresql import insert

from app.database import get_db_session
from app.react.states import DiagnosisResult, ToolInvocation
from app.models.incident_memory import IncidentMemory
from app.core.embedding import _embedder
from app.utils.load_params import load_params

params = load_params("app/params.yml")
_READ_TOOLS = params["save_incident_memory"]["read_tools"]


@tool
async def save_incident_memory(
    incident_id: str,
    symptoms: list[str],
    diagnosis: DiagnosisResult,
    tool_invocations: list[ToolInvocation],
    outcome: str,
    mttr_seconds: int,
) -> str:
    """
    Persist a resolved incident to pgvector so it becomes retrievable
    episodic context for future incidents. Upserts on incident_id.

    Args:
        incident_id:      Unique incident identifier.
        symptoms:         List of symptom strings observed.
        diagnosis:        DiagnosisResult with root_cause_hypothesis.
        tool_invocations: Full audit list of tool calls made.
        outcome:          e.g. 'resolved', 'escalated'.
        mttr_seconds:     Mean time to resolution in seconds.

    Returns:
        Confirmation string with the stored incident_id.
    """
    embed_text = " ".join(symptoms) + " " + diagnosis["root_cause_hypothesis"]
    embedding = await _embedder.aembed_query(embed_text)

    actions_taken = [
        inv["tool_name"]
        for inv in tool_invocations
        if inv["success"] and inv["tool_name"] not in _READ_TOOLS
    ]

    values = {
        "incident_id":   incident_id,
        "symptoms":      symptoms,
        "root_cause":    diagnosis["root_cause_hypothesis"],
        "actions_taken": actions_taken,
        "outcome":       outcome,
        "mttr_seconds":  mttr_seconds,
        "embedding":     embedding,
        "created_at":    datetime.now(timezone.utc),
    }

    stmt = (
        insert(IncidentMemory)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["incident_id"],
            set_={k: v for k, v in values.items() if k != "incident_id"},
        )
    )

    async with get_db_session() as db:
        await db.execute(stmt)
        await db.commit()

    return f"incident_memory saved: {incident_id}"