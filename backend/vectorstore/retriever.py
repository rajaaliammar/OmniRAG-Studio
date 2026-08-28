"""Similarity retriever over ChromaDB collections."""

from __future__ import annotations

from typing import Any, Callable, TypedDict

from backend.vectorstore.chroma_db import get_or_create_collection
from backend.vectorstore.embeddings import embed_query
from backend.vectorstore.errors import VectorStoreError


class RetrievalHit(TypedDict):
    """One similarity-search match."""

    content: str
    metadata: dict[str, Any]
    score: float


def similarity_search(
    query: str,
    collection_name: str,
    k: int = 4,
    score_threshold: float = 0.0,
) -> list[RetrievalHit]:
    """Return the top-k chunks most similar to ``query``.

    Collections are created with cosine space. Chroma distances are converted
    to relevance scores as ``score = 1 - distance`` (cosine similarity).

    Args:
        query: Natural-language search query.
        collection_name: Collection to search.
        k: Maximum number of hits to return.
        score_threshold: Minimum relevance score to keep (inclusive).

    Returns:
        Hits with ``content``, ``metadata``, and ``score``, ordered by
        descending relevance.

    Raises:
        VectorStoreError: If ``query`` is empty, ``k`` is invalid, embedding
            fails, or Chroma cannot be queried.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise VectorStoreError("Cannot run similarity search with an empty query.")
    if k < 1:
        raise VectorStoreError("k must be a positive integer.")

    collection = get_or_create_collection(collection_name)
    try:
        count = collection.count()
    except Exception as exc:
        raise VectorStoreError(
            f"Unable to read collection '{collection.name}': {exc}"
        ) from exc
    if count == 0:
        return []

    try:
        query_vector = embed_query(cleaned)
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(f"Failed to embed search query: {exc}") from exc

    n_results = min(k, count)
    try:
        raw = collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        raise VectorStoreError(
            f"Similarity search failed on '{collection.name}': {exc}"
        ) from exc

    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    hits: list[RetrievalHit] = []
    for content, metadata, distance in zip(
        documents, metadatas, distances, strict=False
    ):
        score = _distance_to_score(distance)
        if score < score_threshold:
            continue
        hits.append(
            RetrievalHit(
                content=content or "",
                metadata=dict(metadata or {}),
                score=score,
            )
        )
    hits.sort(key=lambda hit: hit["score"], reverse=True)
    return hits


def get_retriever(
    k: int = 4,
    collection_name: str = "default_collection",
    score_threshold: float = 0.0,
) -> Callable[[str], list[RetrievalHit]]:
    """Build a callable retriever over a named collection.

    Args:
        k: Maximum number of hits per query.
        collection_name: Collection to search.
        score_threshold: Minimum relevance score to keep.

    Returns:
        A function that accepts a query string and returns retrieval hits.
    """

    def _retrieve(query: str) -> list[RetrievalHit]:
        return similarity_search(
            query,
            collection_name,
            k=k,
            score_threshold=score_threshold,
        )

    return _retrieve


def _distance_to_score(distance: float | None) -> float:
    """Convert a Chroma cosine distance into a similarity score in roughly [0, 1]."""
    if distance is None:
        return 0.0
    return float(1.0 - distance)
