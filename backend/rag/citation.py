"""Source citation formatting for RAG answers."""

from __future__ import annotations

from typing import Any, Mapping

from langchain_core.documents import Document

_SNIPPET_CHARS = 220


def format_citations(documents: list[Any]) -> list[dict[str, Any]]:
    """Turn retrieved hits into citation payloads.

    Each item includes ``source``, ``page/row``, optional ``score``, and a
    short ``snippet`` preview when content is available.

    Args:
        documents: Retriever hits (dicts with ``metadata``) or LangChain
            Documents.

    Returns:
        Deduplicated citation mappings in retrieval order.
    """
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in documents:
        metadata = _metadata_of(item)
        source = str(metadata.get("source") or "unknown").strip() or "unknown"
        locator = _locator(metadata)
        key = (source, locator)
        if key in seen:
            continue
        seen.add(key)
        citation: dict[str, Any] = {"source": source, "page/row": locator}
        score = _score_of(item)
        if score is not None:
            citation["score"] = score
        snippet = _snippet_of(item)
        if snippet:
            citation["snippet"] = snippet
        citations.append(citation)
    return citations


def _metadata_of(item: Any) -> Mapping[str, Any]:
    """Extract a metadata mapping from a hit or Document."""
    if isinstance(item, Document):
        return item.metadata or {}
    if isinstance(item, Mapping):
        meta = item.get("metadata")
        if isinstance(meta, Mapping):
            return meta
        return item
    return {}


def _score_of(item: Any) -> float | None:
    """Return a relevance score when present on a retrieval hit."""
    if isinstance(item, Mapping) and "score" in item:
        try:
            return round(float(item["score"]), 4)
        except (TypeError, ValueError):
            return None
    return None


def _snippet_of(item: Any) -> str:
    """Return a compact text preview from a hit or Document."""
    content = ""
    if isinstance(item, Document):
        content = item.page_content or ""
    elif isinstance(item, Mapping):
        content = str(item.get("content") or item.get("page_content") or "")
    compact = " ".join(content.split())
    if not compact:
        return ""
    if len(compact) <= _SNIPPET_CHARS:
        return compact
    return compact[:_SNIPPET_CHARS].rstrip() + "..."


def _locator(metadata: Mapping[str, Any]) -> str:
    """Return a page number, row index, or URL locator."""
    page = metadata.get("page")
    if page not in (None, ""):
        return str(page)
    row = metadata.get("row_index")
    if row not in (None, ""):
        return str(row)
    source = str(metadata.get("source") or "").strip()
    if source.startswith("http://") or source.startswith("https://"):
        return source
    title = metadata.get("title")
    if title not in (None, ""):
        return str(title)
    return ""
