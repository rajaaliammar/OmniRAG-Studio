"""Local HuggingFace embedding helpers with optional OpenAI fallback.

The sentence-transformers / torch stack is imported only on the first
embed or ingest call so FastAPI ``/docs`` is not blocked at startup.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol, Sequence

from backend.config import get_settings
from backend.vectorstore.errors import VectorStoreError

logger = logging.getLogger(__name__)

DEFAULT_HF_MODEL = "all-MiniLM-L6-v2"
_MAX_RETRIES = 3
_RETRY_BASE_SECONDS = 1.0

# Populated on first use (or patched by unit tests). Never import torch here.
HuggingFaceEmbeddings = None


class EmbeddingsClient(Protocol):
    """Minimal embedding client used by the vector store."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents."""


class HuggingFaceEmbeddingsHolder:
    """Process-wide lazy singleton for CPU HuggingFace embedders."""

    _lock = threading.Lock()
    _clients: dict[str, EmbeddingsClient] = {}

    @classmethod
    def get(cls, model_name: str) -> EmbeddingsClient:
        """Return a cached MiniLM client, loading it on first request only.

        Args:
            model_name: sentence-transformers model id (e.g. ``all-MiniLM-L6-v2``).

        Returns:
            A LangChain embeddings client.

        Raises:
            VectorStoreError: If the local model cannot be loaded.
        """
        cached = cls._clients.get(model_name)
        if cached is not None:
            return cached
        with cls._lock:
            cached = cls._clients.get(model_name)
            if cached is not None:
                return cached
            client = cls._create(model_name)
            cls._clients[model_name] = client
            return client

    @classmethod
    def reset(cls) -> None:
        """Drop cached clients (used by unit tests)."""
        with cls._lock:
            cls._clients.clear()

    @classmethod
    def _create(cls, model_name: str) -> EmbeddingsClient:
        """Import HuggingFaceEmbeddings and load weights (slow; request path)."""
        hf_cls = _resolve_huggingface_cls()
        try:
            client = hf_cls(
                model_name=model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={
                    "normalize_embeddings": True,
                    "batch_size": get_settings().embedding_batch_size,
                },
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Unable to initialize HuggingFace embeddings '{model_name}': {exc}"
            ) from exc
        logger.info(
            "Loaded local HuggingFace embeddings model '%s' on CPU.",
            model_name,
        )
        return client


def _resolve_huggingface_cls() -> type:
    """Import HuggingFaceEmbeddings on first use; honor test patches."""
    global HuggingFaceEmbeddings
    if HuggingFaceEmbeddings is not None:
        return HuggingFaceEmbeddings
    try:
        from langchain_huggingface import HuggingFaceEmbeddings as hf_cls
    except ImportError:  # pragma: no cover - fallback for older LangChain stacks
        from langchain_community.embeddings import HuggingFaceEmbeddings as hf_cls
    HuggingFaceEmbeddings = hf_cls
    return hf_cls


def reset_embedding_clients() -> None:
    """Drop cached local embedding clients (used by unit tests)."""
    HuggingFaceEmbeddingsHolder.reset()


def get_embeddings(model: str | None = None) -> EmbeddingsClient:
    """Return the configured embedding client (cached after first load).

    HuggingFace ``all-MiniLM-L6-v2`` is the default and is constructed only
    when this function is first called (ingest / search), never at import.

    Args:
        model: Optional model override. OpenAI-style names are remapped to
            MiniLM when the provider is HuggingFace.

    Returns:
        A LangChain embeddings client (``embed_query`` / ``embed_documents``).

    Raises:
        VectorStoreError: If the selected provider cannot be initialized.
    """
    settings = get_settings()
    provider = _provider_name(settings.embedding_provider)
    if provider == "openai":
        return _build_openai_client(model)
    return HuggingFaceEmbeddingsHolder.get(_huggingface_model_name(model))


def embed_query(text: str) -> list[float]:
    """Embed a single query string.

    Args:
        text: Query text to embed.

    Returns:
        A single embedding vector.

    Raises:
        VectorStoreError: If the input is empty or embedding fails.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise VectorStoreError("Cannot embed an empty query.")
    vectors = _embed_with_optional_fallback([cleaned], is_query=True)
    return vectors[0]


def embed_documents(
    texts: Sequence[str],
    batch_size: int | None = None,
) -> list[list[float]]:
    """Embed many texts in batches on the local HuggingFace model.

    Args:
        texts: Texts to embed, in order.
        batch_size: Optional override for ``Settings.embedding_batch_size``.

    Returns:
        Embedding vectors aligned with ``texts``.

    Raises:
        VectorStoreError: If ``texts`` is empty or embedding fails.
    """
    if not texts:
        raise VectorStoreError("No texts were provided to embed.")

    settings = get_settings()
    size = batch_size or settings.embedding_batch_size
    if size <= 0:
        raise VectorStoreError("embedding_batch_size must be a positive integer.")

    cleaned = [item.strip() if item and item.strip() else " " for item in texts]
    vectors: list[list[float]] = []
    for start in range(0, len(cleaned), size):
        batch = cleaned[start : start + size]
        vectors.extend(_embed_with_optional_fallback(batch, is_query=False))
    return vectors


def _provider_name(value: str | None) -> str:
    """Normalize the embedding provider setting."""
    return (value or "huggingface").strip().lower()


def _huggingface_model_name(model: str | None) -> str:
    """Resolve a local sentence-transformers model id."""
    settings = get_settings()
    chosen = (model or settings.embedding_model or DEFAULT_HF_MODEL).strip()
    if not chosen or chosen.startswith("text-embedding-"):
        return DEFAULT_HF_MODEL
    if chosen.startswith("sentence-transformers/"):
        return chosen.split("/", maxsplit=1)[1] or DEFAULT_HF_MODEL
    return chosen


def _build_openai_client(model: str | None = None) -> EmbeddingsClient:
    """Build an OpenAI embeddings client (explicit opt-in only)."""
    from langchain_openai import OpenAIEmbeddings

    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()
    if not api_key or api_key == "your_openai_api_key_here":
        raise VectorStoreError(
            "OPENAI_API_KEY is not configured. Set EMBEDDING_PROVIDER=openai "
            "only when a valid OPENAI_API_KEY is present."
        )
    chosen_model = model or settings.embedding_model or "text-embedding-3-small"
    if not chosen_model.startswith("text-embedding-"):
        chosen_model = "text-embedding-3-small"
    try:
        return OpenAIEmbeddings(
            model=chosen_model,
            api_key=api_key,
            chunk_size=settings.embedding_batch_size,
            max_retries=0,
        )
    except Exception as exc:
        raise VectorStoreError(
            f"Unable to initialize OpenAI embedding model '{chosen_model}': {exc}"
        ) from exc


def _embed_with_optional_fallback(
    texts: list[str],
    *,
    is_query: bool,
) -> list[list[float]]:
    """Embed with the primary provider, then optional explicit OpenAI fallback."""
    try:
        return _embed_batch(get_embeddings(), texts, is_query=is_query)
    except VectorStoreError:
        raise
    except Exception as exc:
        settings = get_settings()
        fallback = _provider_name(settings.embedding_fallback_provider)
        primary = _provider_name(settings.embedding_provider)
        if fallback == "openai" and primary != "openai":
            logger.warning(
                "Local embeddings failed (%s); using explicit OpenAI fallback.",
                exc,
            )
            return _embed_batch(
                _build_openai_client(),
                texts,
                is_query=is_query,
                with_retries=True,
            )
        raise VectorStoreError(f"Embedding failed: {exc}") from exc


def _embed_batch(
    embedder: EmbeddingsClient,
    texts: list[str],
    *,
    is_query: bool,
    with_retries: bool = False,
) -> list[list[float]]:
    """Call ``embed_query`` / ``embed_documents``, optionally retrying OpenAI."""
    if not with_retries:
        if is_query:
            return [embedder.embed_query(texts[0])]
        return embedder.embed_documents(texts)
    return _embed_openai_with_retry(embedder, texts, is_query=is_query)


def _embed_openai_with_retry(
    embedder: EmbeddingsClient,
    texts: list[str],
    *,
    is_query: bool,
) -> list[list[float]]:
    """Retry OpenAI calls on rate-limit and connection errors."""
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        RateLimitError,
    )

    delay = _RETRY_BASE_SECONDS
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            if is_query:
                return [embedder.embed_query(texts[0])]
            return embedder.embed_documents(texts)
        except AuthenticationError as exc:
            raise VectorStoreError(
                "OpenAI authentication failed. Check OPENAI_API_KEY."
            ) from exc
        except RateLimitError as exc:
            last_error = exc
            logger.warning(
                "OpenAI rate limit on embed attempt %s/%s.",
                attempt,
                _MAX_RETRIES,
            )
        except (APIConnectionError, APITimeoutError) as exc:
            last_error = exc
            logger.warning(
                "OpenAI connection error on embed attempt %s/%s: %s",
                attempt,
                _MAX_RETRIES,
                exc,
            )
        time.sleep(delay)
        delay *= 2

    raise VectorStoreError(
        "OpenAI embedding API rate-limited or unreachable after retries."
    ) from last_error
