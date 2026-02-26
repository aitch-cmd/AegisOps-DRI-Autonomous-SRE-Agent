"""
Episodic Memory Tool
Embed symptoms → cosine search on IncidentMemory → top-3 past incidents
"""

from langchain_core.tools import tool
from sqlalchemy import select
from app.core.embedding import _embedder
from app.database import get_db_session
from app.react.states import SimilarIncident
from app.models.incident_memory import IncidentMemory
from app.utils.load_params import load_params
params = load_params("app/params.yml")

_SIMILARITY_THRESHOLD = params["retrieve_similar_incidents"]["similarity_threshold"]
_TOP_K = params["retrieve_similar_incidents"]["top_k"]

@tool
async def retrieve_similar_incidents(symptoms: list[str]) -> list[SimilarIncident]:
    """
    Retrieve top-3 past incidents similar to the current symptoms using
    cosine similarity over pgvector embeddings.

    Args:
        symptoms: List of symptom strings from the current incident.

    Returns:
        Top-3 SimilarIncident dicts ordered by similarity score descending.
    """
    embedding = await _embedder.aembed_query(" ".join(symptoms))

    distance = IncidentMemory.embedding.cosine_distance(embedding).label("distance")

    stmt = (
        select(IncidentMemory, distance)
        .where((1 - distance) >= _SIMILARITY_THRESHOLD)
        .order_by(distance)
        .limit(_TOP_K)
    )

    async with get_db_session() as db:
        rows = (await db.execute(stmt)).all()

    return [
        SimilarIncident(
            incident_id=row.IncidentMemory.incident_id,
            symptoms=row.IncidentMemory.symptoms,
            root_cause=row.IncidentMemory.root_cause,
            actions_taken=row.IncidentMemory.actions_taken,
            outcome=row.IncidentMemory.outcome,
            similarity_score=round(1 - row.distance, 4),
        )
        for row in rows
    ]