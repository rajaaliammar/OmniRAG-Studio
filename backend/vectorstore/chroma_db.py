"""Persistent ChromaDB client and collection helpers."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.documents import Document

from backend.config import get_settings
from backend.vectorstore.embeddings import embed_documents
from backend.vectorstore.errors import VectorStoreError

if TYPE_CHECKING:
    from chromadb.api import ClientAPI
    from chromadb.api.models.Collection import Collection

logger = logging.getLogger(__name__)

_CHROMA_ADD_BATCH = 500
_client: ClientAPI | None = None


def get_chroma_client() -> ClientAPI:
    """Return a persistent ChromaDB client using ``CHROMA_DB_PATH``.

    The client is cached for the process lifetime so Windows file locks are
    not stacked on every call.

    Returns:
        A Chroma persistent client.

    Raises:
        VectorStoreError: If the on-disk client cannot be opened.
    """
    global _client
    if _client is not None:
        return _client

    import chromadb
    from chromadb.config import Settings as ChromaSettings

    settings = get_settings()
    path = Path(settings.chroma_db_path).expanduser().resolve()
    try:
        path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    except Exception as exc:
        raise VectorStoreError(
            f"Unable to open ChromaDB at '{path}': {exc}"
        ) from exc
    return _client


def reset_chroma_client() -> None:
    """Drop the cached client (used by unit tests)."""
    global _client
    _client = None


def normalize_collection_name(collection_name: str) -> str:
    """Return a Chroma-safe collection name.

    Args:
        collection_name: Requested collection name.

    Returns:
        A name that satisfies Chroma naming rules.
    """
    settings = get_settings()
    raw = (collection_name or "").strip() or settings.default_collection_name
    raw = raw.replace(" ", "_")
    raw = re.sub(r"[^a-zA-Z0-9._-]", "_", raw)
    raw = re.sub(r"\.{2,}", ".", raw)
    if len(raw) < 3:
        raw = f"col_{raw}"
    if len(raw) > 63:
        raw = raw[:63]
    if not raw[0].isalnum():
        raw = f"c{raw[1:]}"
    if not raw[-1].isalnum():
        raw = f"{raw[:-1]}0"
    return raw


def get_or_create_collection(collection_name: str) -> Collection:
    """Get or create a named Chroma collection (cosine space).

    Args:
        collection_name: Logical collection name. Sanitized before use.

    Returns:
        A Chroma collection handle.

    Raises:
        VectorStoreError: If the collection cannot be created or loaded.
    """
    name = normalize_collection_name(collection_name)
    try:
        client = get_chroma_client()
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(
            f"Unable to get or create collection '{name}': {exc}"
        ) from exc


def add_documents_to_vectorstore(
    collection_name: str,
    documents: list[Document],
) -> int:
    """Embed documents and upsert them into a Chroma collection.

    Args:
        collection_name: Target collection (created if missing).
        documents: LangChain documents (typically splitter chunks).

    Returns:
        Number of chunks written to the collection.

    Raises:
        VectorStoreError: If embedding or Chroma writes fail, or ``documents``
            is empty.
    """
    payloads = [doc for doc in documents if (doc.page_content or "").strip()]
    if not payloads:
        raise VectorStoreError("No documents with text were provided to index.")

    collection = get_or_create_collection(collection_name)
    texts = [doc.page_content.strip() for doc in payloads]
    try:
        vectors = embed_documents(texts)
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(f"Failed to embed documents: {exc}") from exc

    if len(vectors) != len(texts):
        raise VectorStoreError(
            "Embedding count does not match document count "
            f"({len(vectors)} != {len(texts)})."
        )

    ids = [str(uuid.uuid4()) for _ in payloads]
    metadatas = [_chroma_metadata(doc.metadata) for doc in payloads]

    try:
        for start in range(0, len(ids), _CHROMA_ADD_BATCH):
            end = start + _CHROMA_ADD_BATCH
            collection.add(
                ids=ids[start:end],
                embeddings=vectors[start:end],
                documents=texts[start:end],
                metadatas=metadatas[start:end],
            )
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(
            f"Failed to write documents to collection "
            f"'{collection.name}': {exc}"
        ) from exc

    logger.info(
        "Indexed %s chunks into Chroma collection '%s'.",
        len(ids),
        collection.name,
    )
    return len(ids)


def delete_collection(collection_name: str) -> None:
    """Delete a Chroma collection.

    Args:
        collection_name: Collection to drop (sanitized like create).

    Raises:
        VectorStoreError: If the collection does not exist or cannot be deleted.
    """
    name = normalize_collection_name(collection_name)
    try:
        get_chroma_client().delete_collection(name)
    except Exception as exc:
        raise VectorStoreError(
            f"Unable to delete collection '{name}': {exc}"
        ) from exc
    logger.info("Deleted Chroma collection '%s'.", name)


def list_collections() -> list[str]:
    """List persisted collection names.

    Returns:
        Sorted collection names.

    Raises:
        VectorStoreError: If the client cannot list collections.
    """
    try:
        collections = get_chroma_client().list_collections()
    except Exception as exc:
        raise VectorStoreError(f"Unable to list collections: {exc}") from exc
    names: list[str] = []
    for collection in collections:
        if isinstance(collection, str):
            names.append(collection)
        else:
            names.append(collection.name)
    return sorted(names)


def _chroma_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce LangChain metadata into Chroma-supported scalar values."""
    clean: dict[str, str | int | float | bool] = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[str(key)] = value
        else:
            clean[str(key)] = str(value)
    if "source" not in clean:
        clean["source"] = "unknown"
    return clean
