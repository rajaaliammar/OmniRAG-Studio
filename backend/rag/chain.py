"""Retrieval-augmented generation chain with grounded citations."""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.config import get_openai_api_key, get_settings
from backend.rag.citation import format_citations
from backend.rag.errors import RagError
from backend.rag.memory import get_memory
from backend.rag.prompts import GROUNDED_SYSTEM_PROMPT, build_grounded_user_prompt
from backend.vectorstore.errors import VectorStoreError
from backend.vectorstore.retriever import RetrievalHit, similarity_search

logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = (
    "I could not find relevant information in the indexed sources for this "
    "question. Ingest documents into this collection and try again."
)

_llm_lock = threading.Lock()
_llm_client: Any | None = None
_llm_client_key: tuple[str, str] | None = None


@dataclass
class RagResult:
    """Answer payload returned by the RAG chain."""

    answer: str
    citations: list[dict[str, str]] = field(default_factory=list)
    session_id: str = ""


def answer_query(
    query: str,
    collection_name: str,
    session_id: str | None = None,
    k: int | None = None,
    score_threshold: float | None = None,
) -> RagResult:
    """Retrieve context, generate a grounded answer, and record memory.

    Args:
        query: User question.
        collection_name: Chroma collection to search.
        session_id: Optional conversation id. A new UUID is created if omitted.
        k: Optional override for ``Settings.rag_top_k``.
        score_threshold: Optional override for ``Settings.rag_score_threshold``.

    Returns:
        Answer text, retrieval citations, and the session id.

    Raises:
        ValueError: If ``query`` is empty.
        VectorStoreError: If retrieval fails.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("Query must not be empty.")

    settings = get_settings()
    collection = (collection_name or "").strip() or settings.default_collection_name
    sid = (session_id or "").strip() or str(uuid.uuid4())
    top_k = k if k is not None else settings.rag_top_k
    threshold = (
        score_threshold
        if score_threshold is not None
        else settings.rag_score_threshold
    )

    memory = get_memory()
    history_text = memory.format_for_prompt(sid)

    try:
        hits = similarity_search(
            cleaned,
            collection,
            k=top_k,
            score_threshold=threshold,
        )
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(f"Retrieval failed: {exc}") from exc

    if not hits:
        memory.append(sid, "user", cleaned)
        memory.append(sid, "assistant", NO_CONTEXT_ANSWER)
        return RagResult(answer=NO_CONTEXT_ANSWER, citations=[], session_id=sid)

    context = _format_context(hits)
    citations = format_citations(hits)
    answer = _generate_answer(cleaned, context, history_text, hits)
    memory.append(sid, "user", cleaned)
    memory.append(sid, "assistant", answer)
    return RagResult(answer=answer, citations=citations, session_id=sid)


def build_rag_chain() -> Any:
    """Return a callable that runs :func:`answer_query`.

    Returns:
        A function ``(query, collection_name, session_id=None) -> RagResult``.
    """

    def _run(
        query: str,
        collection_name: str = "default_collection",
        session_id: str | None = None,
    ) -> RagResult:
        return answer_query(query, collection_name, session_id)

    return _run


def reset_llm_client() -> None:
    """Drop the cached chat model (used by unit tests)."""
    global _llm_client, _llm_client_key
    with _llm_lock:
        _llm_client = None
        _llm_client_key = None


def _format_context(hits: list[RetrievalHit]) -> str:
    """Number retrieved passages so the model can cite [1], [2], ..."""
    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        meta = hit.get("metadata") or {}
        source = meta.get("source", "unknown")
        locator = ""
        if meta.get("page") not in (None, ""):
            locator = f" page={meta['page']}"
        elif meta.get("row_index") not in (None, ""):
            locator = f" row={meta['row_index']}"
        blocks.append(
            f"[{index}] source={source}{locator}\n{hit.get('content', '').strip()}"
        )
    return "\n\n".join(blocks)


def _generate_answer(
    question: str,
    context: str,
    history: str,
    hits: list[RetrievalHit],
) -> str:
    """Call the configured LLM, or extract sentences from retrieved chunks.

    Missing API keys, HTTP 429, and ``insufficient_quota`` fall back to
    extractive QA so the chat API can still return HTTP 200 with citations.
    """
    try:
        llm = _get_chat_model()
        if llm is None:
            logger.info("No chat LLM configured; using extractive fallback.")
            return _extractive_answer(question, hits)
        from langchain_core.messages import HumanMessage, SystemMessage

        user_prompt = build_grounded_user_prompt(question, context, history)
        response = llm.invoke(
            [
                SystemMessage(content=GROUNDED_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        text = _message_text(response)
        if text:
            return text
        logger.warning("LLM returned an empty answer; using extractive fallback.")
        return _extractive_answer(question, hits)
    except Exception as exc:
        if _is_llm_quota_or_inactive_error(exc):
            logger.warning(
                "OpenAI unavailable (%s); using extractive fallback.",
                exc,
            )
            return _extractive_answer(question, hits)
        logger.warning(
            "LLM generation failed (%s); using extractive fallback.",
            exc,
        )
        return _extractive_answer(question, hits)


_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "for",
    "to",
    "of",
    "in",
    "on",
    "is",
    "are",
    "was",
    "were",
    "be",
    "as",
    "at",
    "by",
    "from",
    "that",
    "this",
    "it",
    "with",
    "what",
    "which",
    "how",
    "much",
    "many",
}


def _tokenize(text: str) -> set[str]:
    """Return lowercase alphanumeric tokens, dropping short stopwords."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {token for token in tokens if len(token) > 1 and token not in _STOPWORDS}


def _split_sentences(text: str) -> list[str]:
    """Split a chunk into sentences; keep the whole chunk if it has no stops."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences = [part.strip() for part in parts if part.strip()]
    return sentences or [cleaned]


def _extractive_answer(question: str, hits: list[RetrievalHit]) -> str:
    """Pick query-overlapping sentences from retrieved chunks, with [n] cites."""
    query_tokens = _tokenize(question)
    scored: list[tuple[float, int, str]] = []
    for index, hit in enumerate(hits, start=1):
        content = (hit.get("content") or "").strip()
        for sentence in _split_sentences(content):
            overlap = len(query_tokens & _tokenize(sentence))
            if query_tokens and overlap == 0:
                continue
            score = overlap / max(len(query_tokens), 1)
            scored.append((score, index, sentence))

    selected: list[str] = []
    seen: set[str] = set()
    for _score, index, sentence in sorted(scored, key=lambda item: item[0], reverse=True):
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(f"{sentence} [{index}]")
        if len(selected) >= 4:
            break

    if not selected:
        for index, hit in enumerate(hits, start=1):
            content = (hit.get("content") or "").strip()
            if not content:
                continue
            lead = _split_sentences(content)[0]
            selected.append(f"{lead} [{index}]")
            if len(selected) >= 3:
                break

    if not selected:
        return NO_CONTEXT_ANSWER
    return " ".join(selected)


def _is_llm_quota_or_inactive_error(exc: BaseException) -> bool:
    """True for missing/invalid keys, HTTP 429, and insufficient_quota."""
    markers = (
        "insufficient_quota",
        "quota exceeded",
        "you exceeded your current quota",
        "rate_limit",
        "rate limit",
        "error code: 429",
        "status code: 429",
        "status code 429",
        "http 429",
        "invalid_api_key",
        "incorrect api key",
        "authentication",
    )
    quota_types = {
        "RateLimitError",
        "AuthenticationError",
        "PermissionDeniedError",
        "APIStatusError",
    }
    for item in _exception_chain(exc):
        if type(item).__name__ in quota_types:
            return True
        status = getattr(item, "status_code", None)
        if status == 429:
            return True
        code = str(getattr(item, "code", "") or "").lower()
        if code in {"insufficient_quota", "rate_limit_exceeded", "invalid_api_key"}:
            return True
        text = str(item).lower()
        if any(marker in text for marker in markers):
            return True
    return False


def _exception_chain(exc: BaseException) -> list[BaseException]:
    """Walk __cause__ / __context__ without looping."""
    chain: list[BaseException] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _message_text(response: Any) -> str:
    """Normalize a LangChain message or raw string to plain text."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "".join(parts).strip()
    return str(content or "").strip()


def _get_chat_model() -> Any | None:
    """Lazily construct ChatOpenAI when the provider and API key are set."""
    global _llm_client, _llm_client_key
    settings = get_settings()
    provider = (settings.llm_provider or "openai").strip().lower()
    if provider in {"extractive", "none", "off"}:
        return None
    api_key = get_openai_api_key()
    if not api_key or api_key == "your_openai_api_key_here":
        return None
    cache_key = (provider, settings.llm_model)
    if _llm_client is not None and _llm_client_key == cache_key:
        return _llm_client
    with _llm_lock:
        if _llm_client is not None and _llm_client_key == cache_key:
            return _llm_client
        if provider != "openai":
            raise RagError(
                f"Unsupported LLM_PROVIDER '{provider}'. Use 'openai' or 'extractive'."
            )
        try:
            from langchain_openai import ChatOpenAI

            _llm_client = ChatOpenAI(
                model=settings.llm_model,
                api_key=api_key,
                temperature=0,
            )
            _llm_client_key = cache_key
        except Exception as exc:
            raise RagError(
                f"Unable to initialize chat model '{settings.llm_model}': {exc}"
            ) from exc
        logger.info("Initialized chat LLM '%s'.", settings.llm_model)
        return _llm_client
