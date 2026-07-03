"""Semantic retrieval over document chunks using pgvector cosine distance."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentChunk
from app.rag.embeddings import embed_query


@dataclass
class RetrievedChunk:
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    distance: float


def retrieve(db: Session, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    """Return the top-k most similar chunks to the query."""
    k = top_k or settings.retrieval_top_k
    query_vector = embed_query(query)

    # pgvector cosine distance operator via SQLAlchemy.
    distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(DocumentChunk, Document.title, distance)
        .join(Document, Document.id == DocumentChunk.document_id)
        .order_by(distance)
        .limit(k)
    )

    results: list[RetrievedChunk] = []
    for chunk, title, dist in db.execute(stmt).all():
        results.append(
            RetrievedChunk(
                document_id=str(chunk.document_id),
                document_title=title,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                distance=float(dist),
            )
        )
    return results
