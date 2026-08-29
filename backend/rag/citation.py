"""Source citation formatting for RAG answers."""

from __future__ import annotations

from typing import Any, Mapping

from langchain_core.documents import Document


def format_citations(documents: list[Any]) -> list[dict[str, str]]:
    """Turn retrieved hits into citation payloads.

    Each item is ``{"source": "...", "page/row": "..."}``. The locator is a
    page number, CSV row index, or URL when those metadata fields exist.

    Args:
        documents: Retriever hits (dicts with ``metadata``) or LangChain
            Documents.

    Returns:
        Deduplicated citation mappings in retrieval order.
    """
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in documents:
        metadata = _metadata_of(item)
        source = str(metadata.get("source") or "unknown").strip() or "unknown"
        locator = _locator(metadata)
        key = (source, locator)
        if key in seen:
            continue
        seen.add(key)
        citations.append({"source": source, "page/row": locator})
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
