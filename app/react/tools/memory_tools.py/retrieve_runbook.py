"""
Semantic RAG Tool
Embed query → cosine search on KnowledgeBase → top-4 relevant chunks
"""

from langchain_core.tools import tool
from sqlalchemy import select
from app.core.embedding import _embedder
from app.database import get_db_session
from app.models.knowledge_base import KnowledgeBase
from app.utils.load_params import load_params

params = load_params("app/params.yml")
_SIMILARITY_THRESHOLD = params["retrieve_runbook"]["similarity_threshold"]
_TOP_K = params["retrieve_runbook"]["top_k"]
_CATEGORIES = params["retrieve_runbook"]["categories"]

@tool
async def retrieve_runbook(query: str) -> list[str]:
    """
    Semantic RAG retrieval over chunked runbooks, architecture docs,
    postmortems, and policy documents.

    Args:
        query: Natural language query, e.g. 'payment service memory leak fix'.

    Returns:
        List of relevant text chunks (max 4, similarity >= 0.75), each
        prefixed with its source category and document name.
    """
    embedding = await _embedder.aembed_query(query)

    distance = KnowledgeBase.embedding.cosine_distance(embedding).label("distance")

    stmt = (
        select(KnowledgeBase, distance)
        .where(KnowledgeBase.category.in_(_CATEGORIES))
        .where((1 - distance) >= _SIMILARITY_THRESHOLD)
        .order_by(distance)
        .limit(_TOP_K)
    )

    async with get_db_session() as db:
        rows = (await db.execute(stmt)).all()

    return [
        f"[{row.KnowledgeBase.category} / {row.KnowledgeBase.doc_name}]\n{row.KnowledgeBase.chunk_text}"
        for row in rows
    ]