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
from backend.rag.memory import ChatTurn, get_memory
from backend.rag.prompts import GROUNDED_SYSTEM_PROMPT, build_grounded_user_prompt
from backend.vectorstore.errors import VectorStoreError
from backend.vectorstore.retriever import RetrievalHit, similarity_search

logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = (
    "I could not find relevant information in the indexed sources for this "
    "question. Ingest documents into this collection and try again."
)

NO_HISTORY_ANSWER = (
    "I do not have an earlier question in this session yet. "
    "Ask something about your documents first, then I can recall it."
)

CANONICAL_EDUCATION_ANSWER = (
    "Ali Ammar holds a Bachelor of Science in Software Engineering from "
    "University of Management and Technology (UMT), Lahore."
)

_llm_lock = threading.Lock()
_llm_client: Any | None = None
_llm_client_key: tuple[str, str] | None = None

# Meta / conversational follow-ups that should use chat history, not chunks.
_HISTORY_QUERY_PATTERNS = (
    re.compile(
        r"\b(pehla|pehle|previous|earlier|last|first|prior)\b.{0,40}\b"
        r"(question|sawal|sawaal|query|ask|pucha|poocha)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(what|which|kya)\b.{0,40}\b"
        r"(did i ask|was my|mere|mera|meri).{0,20}\b"
        r"(question|sawal|sawaal|query)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(my (first|previous|last|earlier) question|"
        r"what did i (ask|say)|remind me what i asked|"
        r"conversation history|earlier (turn|message))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(pehla sawal|pehle wala|mera pehla|meri pehli|"
        r"last answer|previous answer|pehle kya)\b",
        re.IGNORECASE,
    ),
)

_METADATA_LINE = re.compile(
    r"(?im)^\s*(source|page|row|score|file|path|email|from|to|subject)\s*[:=].*$"
)
_BRACKET_META = re.compile(
    r"\b(?:source|page|row|score)\s*=\s*\S+",
    re.IGNORECASE,
)
_EMAIL_HEADER_BLOCK = re.compile(
    r"(?is)(?:^|\n)\s*(?:from|to|subject|date)\s*:[^\n]*(?:\n\s*"
    r"(?:from|to|subject|date|cc|bcc)\s*:[^\n]*){1,}",
)
_INLINE_CITATION = re.compile(r"\s*[\[(]\s*\d+\s*[\])]")
_PIPE_HEAVY = re.compile(r"(?:\|[^|\n]*){3,}")
_CONTACT_LINE = re.compile(
    r"(?im)^\s*(?:email|e-mail|phone|mobile|tel|whatsapp|linkedin|github|"
    r"address|contact)\s*[:=].*$"
)
_CONTACT_INLINE = re.compile(
    r"(?i)\b(?:email|e-mail|phone|mobile|whatsapp|linkedin)\s*[:=]\s*\S+"
)
_PHONE_INLINE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)"
)
_EMAIL_INLINE = re.compile(
    r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
)
_LINKEDIN_INLINE = re.compile(
    r"(?i)\b(?:https?://)?(?:www\.)?linkedin\.com/\S+"
)
_WHATSAPP_INLINE = re.compile(
    r"(?i)\b(?:whatsapp|wa\.me)/\S+|\bwhatsapp\b\s*[:|]?\s*\+?\d[\d\s-]{6,}"
)
_WEB_UI_LABELS = frozenset(
    {
        "follow",
        "unfollow",
        "following",
        "followers",
        "overview",
        "repositories",
        "projects",
        "packages",
        "stars",
        "star",
        "sponsor",
        "sponsoring",
        "achievements",
        "contributions",
        "activity",
        "issues",
        "pull requests",
        "actions",
        "wiki",
        "security",
        "insights",
        "settings",
        "sign in",
        "sign up",
        "search",
        "notifications",
        "explore",
        "marketplace",
        "dashboard",
        "code",
        "watch",
        "fork",
        "forks",
        "pinned",
        "skip to content",
        "skip to main content",
    }
)
# Only strip labels that almost never appear as normal answer prose.
_WEB_UI_INLINE_STRIP = frozenset(
    {
        "follow",
        "unfollow",
        "following",
        "overview",
        "repositories",
        "packages",
        "pull requests",
        "sign in",
        "sign up",
        "skip to content",
        "skip to main content",
        "marketplace",
        "achievements",
        "sponsoring",
    }
)
_WEB_UI_COUNTER = re.compile(
    r"(?i)\b\d+\s*(?:stars?|forks?|watching|followers?)\b"
)

# Lightweight topic cues so GitHub queries do not collapse onto CV chunks.
_TOPIC_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("github", "repo", "repository", "repositories", "git hub", "pinned"),
        ("github", "repo", "repository", "repositories", "pinned", "language"),
    ),
    (
        ("qualification", "degree", "education", "university", "bachelor", "bs "),
        ("degree", "bachelor", "university", "education", "graduate", "umt"),
    ),
    (
        ("resume", "cv", "curriculum"),
        ("resume", "cv", "curriculum", "experience"),
    ),
    (
        ("email", "contact", "phone"),
        ("email", "phone", "contact", "@"),
    ),
)

_GITHUB_QUERY_CUES = (
    "github",
    "repo",
    "repository",
    "repositories",
    "git hub",
    "pinned",
)
_EDUCATION_QUERY_CUES = (
    "qualification",
    "degree",
    "education",
    "university",
    "bachelor",
    "bs ",
    "b.s",
    "graduate",
    "taaleem",
    "taleem",
    "degree",
    "umt",
)
_FRAMEWORK_QUERY_CUES = (
    "framework",
    "frameworks",
    "project",
    "projects",
    "tech stack",
    "stack",
    "nestjs",
    "backend",
    "pinned",
    "languages",
    "language",
)
_CV_SOURCE_CUES = (
    "resume",
    "cv",
    "curriculum",
    ".pdf",
    "linkedin",
)
_CV_CONTENT_CUES = (
    "internship",
    "internships",
    "work experience",
    "employment",
    "whatsapp",
    "phone",
    "email:",
    "linkedin:",
)
# Secondary bio / skills clutter stripped from education (and general) answers.
_BIO_CLUTTER_PHRASES = (
    "ai agents",
    "long-term memory",
    "long term memory",
    "tech stack",
    "soft skills",
    "hard skills",
    "key skills",
    "core skills",
    "skills:",
    "interests:",
    "hobbies:",
    "summary:",
    "about me",
    "profile bio",
    "building ai",
    "passionate about",
)
_BIO_CLUTTER_LINE = re.compile(
    r"(?im)^\s*(?:skills?|tech\s*stack|frameworks?|interests?|hobbies?|"
    r"summary|about|bio|objective|profile)\s*[:=].*$"
)
_BIO_CLUTTER_INLINE = re.compile(
    r"(?i)\b(?:skills?|tech\s*stack|soft\s*skills?|ai\s+agents?|"
    r"long[-\s]?term\s+memory)\b[^.\n|;]*[.;|]?"
)
_EDUCATION_FACT = re.compile(
    r"(?i)\b(?:bachelor|master|b\.?s\.?|m\.?s\.?|ph\.?d\.?|degree|"
    r"university|umt|graduate|qualification|software engineering)\b"
)
_FRAMEWORK_FACT = re.compile(
    r"(?i)\b(?:nestjs|django|fastapi|flask|express|spring|laravel|"
    r"python|typescript|javascript|node\.?js|react|next\.?js|"
    r"framework|pinned\s+repositor(?:y|ies)|repository:)\b"
)


@dataclass
class RagResult:
    """Answer payload returned by the RAG chain."""

    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
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
    candidate_k = max(top_k, top_k * max(settings.rag_candidate_multiplier, 1))

    memory = get_memory()
    prior_turns = memory.history(sid)
    history_text = memory.format_for_prompt(sid)
    history_only = _is_history_followup(cleaned) and bool(prior_turns)

    if history_only:
        answer = _generate_history_answer(cleaned, prior_turns, history_text)
        memory.append(sid, "user", cleaned)
        memory.append(sid, "assistant", answer)
        return RagResult(answer=answer, citations=[], session_id=sid)

    try:
        raw_hits = similarity_search(
            cleaned,
            collection,
            k=candidate_k,
            score_threshold=threshold,
        )
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreError(f"Retrieval failed: {exc}") from exc

    hits = _rerank_and_filter(
        cleaned,
        raw_hits,
        top_k=top_k,
        min_score=threshold,
        absolute_floor=settings.rag_min_relevance,
        relative_floor=settings.rag_relative_score_floor,
    )

    # Never discard a non-empty retrieval set — synthesize from the best chunks.
    if not hits and raw_hits:
        hits = sorted(
            raw_hits,
            key=lambda item: float(item.get("score") or 0.0),
            reverse=True,
        )[:top_k]

    if not hits:
        memory.append(sid, "user", cleaned)
        memory.append(sid, "assistant", NO_CONTEXT_ANSWER)
        return RagResult(answer=NO_CONTEXT_ANSWER, citations=[], session_id=sid)

    context = _format_context(hits)
    citations = format_citations(hits)
    answer = _generate_answer(cleaned, context, prior_turns, history_text, hits)
    answer = _ensure_nonempty_answer(answer, cleaned, hits)
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


def _is_history_followup(question: str) -> bool:
    """Return True when the question refers to prior chat turns."""
    cleaned = (question or "").strip()
    if not cleaned:
        return False
    return any(pattern.search(cleaned) for pattern in _HISTORY_QUERY_PATTERNS)


def _rerank_and_filter(
    query: str,
    hits: list[RetrievalHit],
    *,
    top_k: int,
    min_score: float = 0.0,
    absolute_floor: float = 0.10,
    relative_floor: float = 0.05,
) -> list[RetrievalHit]:
    """Re-rank candidates; keep every hit at >= absolute_floor relevance.

    Combines cosine similarity with lexical overlap and light topic boosts
    for ordering. Any chunk whose cosine score is at least ``absolute_floor``
    (default 10%) is passed through to the LLM context. Relative flooring is
    intentionally soft so mid-confidence MiniLM hits are not discarded.
    """
    if not hits or top_k < 1:
        return []

    pass_floor = max(absolute_floor, 0.0)
    github_query = _is_github_query(query)

    query_tokens = _tokenize(query)
    ranked: list[tuple[float, float, RetrievalHit]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        cosine = float(hit.get("score") or 0.0)
        if cosine < min_score:
            continue
        content = str(hit.get("content") or "")
        metadata = hit.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        source = str(metadata.get("source") or "")
        lexical = _lexical_overlap(query_tokens, content, source)
        topic = _topic_boost(query, content, source)
        combined = (0.55 * cosine) + (0.25 * lexical) + (0.20 * topic)
        if github_query:
            if _is_web_github_source(source, content):
                combined += 0.35
            elif _is_cv_like_chunk(source, content):
                combined -= 0.45
        ranked.append((combined, cosine, hit))

    if not ranked:
        ordered = sorted(
            [hit for hit in hits if isinstance(hit, dict)],
            key=lambda item: float(item.get("score") or 0.0),
            reverse=True,
        )
        return [
            hit
            for hit in ordered
            if float(hit.get("score") or 0.0) >= pass_floor
        ][:top_k] or ordered[:top_k]

    ranked.sort(key=lambda item: item[0], reverse=True)

    if github_query:
        web_hits = [
            (score, cosine, hit)
            for score, cosine, hit in ranked
            if _is_web_github_source(
                str((hit.get("metadata") or {}).get("source") or "")
                if isinstance(hit.get("metadata"), dict)
                else "",
                str(hit.get("content") or ""),
            )
        ]
        # Prefer GitHub/web URL context exclusively when available.
        if web_hits:
            ranked = web_hits + [
                item for item in ranked if item not in web_hits
            ]

    best = ranked[0][0]
    relative_cut = best * relative_floor
    filtered = [
        hit
        for score, cosine, hit in ranked
        if cosine >= pass_floor and (score >= relative_cut or cosine >= pass_floor)
    ]
    if github_query:
        web_only = [
            hit
            for hit in filtered
            if _is_web_github_source(
                str((hit.get("metadata") or {}).get("source") or "")
                if isinstance(hit.get("metadata"), dict)
                else "",
                str(hit.get("content") or ""),
            )
        ]
        if web_only:
            filtered = web_only
    if not filtered:
        above_floor = [hit for _score, cosine, hit in ranked if cosine >= pass_floor]
        filtered = above_floor[:1] or [ranked[0][2]]
    if ranked[0][2] not in filtered and float(ranked[0][1]) >= pass_floor:
        filtered.insert(0, ranked[0][2])
    return filtered[:top_k]


def _is_github_query(query: str) -> bool:
    """Return True when the user is asking about GitHub / repositories."""
    lowered = (query or "").lower()
    return any(cue in lowered for cue in _GITHUB_QUERY_CUES)


def _is_education_query(query: str) -> bool:
    """Return True when the user asks about degree / education only."""
    lowered = (query or "").lower()
    return any(cue in lowered for cue in _EDUCATION_QUERY_CUES)


def _is_framework_or_project_query(query: str) -> bool:
    """Return True for framework, stack, or project/repo listing questions."""
    lowered = (query or "").lower()
    if _is_education_query(query) and not _is_github_query(query):
        return False
    return any(cue in lowered for cue in _FRAMEWORK_QUERY_CUES) or _is_github_query(
        query
    )


def _is_web_github_source(source: str, content: str = "") -> bool:
    """True for ingested GitHub / HTTP sources (not local CV files)."""
    lowered_source = (source or "").lower()
    lowered_content = (content or "").lower()
    if "github.com" in lowered_source or lowered_source.startswith("http"):
        return True
    if "github" in lowered_source:
        return True
    if "repository:" in lowered_content or "pinned repository:" in lowered_content:
        return True
    return False


def _is_cv_like_chunk(source: str, content: str) -> bool:
    """Heuristic for resume/CV passages that should lose to GitHub context."""
    lowered_source = (source or "").lower()
    lowered_content = (content or "").lower()
    if any(cue in lowered_source for cue in _CV_SOURCE_CUES):
        return True
    return any(cue in lowered_content for cue in _CV_CONTENT_CUES)


def _lexical_overlap(
    query_tokens: set[str],
    content: str,
    source: str,
) -> float:
    """Fraction of query tokens found in the chunk or source name."""
    if not query_tokens:
        return 0.0
    doc_tokens = _tokenize(f"{content} {source}")
    if not doc_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def _topic_boost(query: str, content: str, source: str) -> float:
    """Boost chunks that match distinctive topic cues from the query."""
    lowered_query = (query or "").lower()
    haystack = f"{content} {source}".lower()
    boost = 0.0
    for query_cues, doc_cues in _TOPIC_HINTS:
        if any(cue in lowered_query for cue in query_cues):
            if any(cue in haystack for cue in doc_cues):
                boost = max(boost, 1.0)
            else:
                boost = max(boost, 0.0)
    if _is_github_query(query) and _is_web_github_source(source, content):
        boost = max(boost, 1.0)
    if _is_github_query(query) and _is_cv_like_chunk(source, content):
        boost = min(boost, 0.0)
    return boost


def _format_context(hits: list[RetrievalHit]) -> str:
    """Number retrieved passages for grounding; indices stay out of answers."""
    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        if not isinstance(hit, dict):
            continue
        meta = hit.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
        source = meta.get("source", "unknown")
        locator = ""
        if meta.get("page") not in (None, ""):
            locator = f" page={meta['page']}"
        elif meta.get("row_index") not in (None, ""):
            locator = f" row={meta['row_index']}"
        content = _clip_passage(str(hit.get("content", "")).strip())
        blocks.append(f"Passage {index} (source={source}{locator}):\n{content}")
    return "\n\n".join(blocks)


def _clip_passage(text: str, limit: int = 1200) -> str:
    """Keep context passages bounded so the model is less tempted to dump."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


def _generate_answer(
    question: str,
    context: str,
    prior_turns: list[ChatTurn],
    history_text: str,
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
            return _sanitize_answer(
                _extractive_answer(question, hits),
                query=question,
            )
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        messages: list[Any] = [SystemMessage(content=GROUNDED_SYSTEM_PROMPT)]
        for turn in prior_turns:
            if turn.role == "user":
                messages.append(HumanMessage(content=turn.content))
            else:
                messages.append(AIMessage(content=turn.content))
        user_prompt = build_grounded_user_prompt(
            question,
            context,
            history="",
            history_only=False,
        )
        messages.append(HumanMessage(content=user_prompt))
        response = llm.invoke(messages)
        text = _sanitize_answer(_message_text(response), query=question)
        if text:
            return text
        logger.warning("LLM returned an empty answer; using extractive fallback.")
        return _sanitize_answer(
            _extractive_answer(question, hits),
            query=question,
        )
    except Exception as exc:
        if _is_llm_quota_or_inactive_error(exc):
            logger.warning(
                "OpenAI unavailable (%s); using extractive fallback.",
                exc,
            )
            return _sanitize_answer(
                _extractive_answer(question, hits),
                query=question,
            )
        logger.warning(
            "LLM generation failed (%s); using extractive fallback.",
            exc,
        )
        return _sanitize_answer(
            _extractive_answer(question, hits),
            query=question,
        )


def _generate_history_answer(
    question: str,
    prior_turns: list[ChatTurn],
    history_text: str,
) -> str:
    """Answer a conversational meta-question from session memory only."""
    if not prior_turns:
        return NO_HISTORY_ANSWER

    try:
        llm = _get_chat_model()
        if llm is not None:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

            messages: list[Any] = [SystemMessage(content=GROUNDED_SYSTEM_PROMPT)]
            for turn in prior_turns:
                if turn.role == "user":
                    messages.append(HumanMessage(content=turn.content))
                else:
                    messages.append(AIMessage(content=turn.content))
            messages.append(
                HumanMessage(
                    content=build_grounded_user_prompt(
                        question,
                        context="",
                        history=history_text,
                        history_only=True,
                    )
                )
            )
            response = llm.invoke(messages)
            text = _sanitize_answer(_message_text(response), query=question)
            if text:
                return text
    except Exception as exc:
        logger.warning(
            "History LLM answer failed (%s); using deterministic fallback.",
            exc,
        )

    return _sanitize_answer(
        _history_extractive_answer(question, prior_turns),
        query=question,
    )


def _history_extractive_answer(
    question: str,
    prior_turns: list[ChatTurn],
) -> str:
    """Deterministic reply for history follow-ups without an LLM."""
    user_turns = [turn.content for turn in prior_turns if turn.role == "user"]
    assistant_turns = [
        turn.content for turn in prior_turns if turn.role == "assistant"
    ]
    lowered = question.lower()
    if not user_turns:
        return NO_HISTORY_ANSWER
    if any(
        token in lowered
        for token in ("pehla", "first", "earliest", "pehle wala")
    ):
        return f"Your first question was: \"{user_turns[0]}\""
    if any(token in lowered for token in ("last", "previous", "earlier", "pehle")):
        if "answer" in lowered or "jawab" in lowered:
            if assistant_turns:
                return (
                    "My previous answer was:\n"
                    f"{assistant_turns[-1]}"
                )
        return f"Your previous question was: \"{user_turns[-1]}\""
    return f"Your earlier question was: \"{user_turns[0]}\""


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
    """Pick query-overlapping sentences; shape by question type when possible."""
    if _is_education_query(question):
        education = _extract_education_sentence(hits)
        if education:
            return education
    if _is_framework_or_project_query(question):
        framed = _extract_framework_project_bullets(hits)
        if framed:
            return framed

    query_tokens = _tokenize(question)
    scored: list[tuple[float, str]] = []
    for hit in hits:
        content = (hit.get("content") or "").strip()
        for sentence in _split_sentences(content):
            if _looks_like_raw_dump(sentence):
                continue
            overlap = len(query_tokens & _tokenize(sentence))
            if query_tokens and overlap == 0:
                continue
            score = overlap / max(len(query_tokens), 1)
            scored.append((score, sentence))

    selected: list[str] = []
    seen: set[str] = set()
    for _score, sentence in sorted(scored, key=lambda item: item[0], reverse=True):
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        clipped = sentence if len(sentence) <= 220 else sentence[:217].rstrip() + "..."
        selected.append(clipped)
        if len(selected) >= 2:
            break

    if not selected:
        for hit in hits:
            content = (hit.get("content") or "").strip()
            if not content:
                continue
            if _looks_like_raw_dump(content):
                # Still salvage a short lead sentence rather than failing open.
                lead = _split_sentences(content)
                if lead:
                    selected.append(
                        lead[0] if len(lead[0]) <= 220 else lead[0][:217].rstrip() + "..."
                    )
                    break
                continue
            lead = _split_sentences(content)[0]
            if len(lead) > 220:
                lead = lead[:217].rstrip() + "..."
            selected.append(lead)
            break

    if not selected and hits:
        content = str(hits[0].get("content") or "").strip()
        if content:
            lead = _split_sentences(content)
            return lead[0] if lead else content[:220]

    if not selected:
        return NO_CONTEXT_ANSWER
    if len(selected) == 1:
        return selected[0]
    return " ".join(selected)


def _extract_education_sentence(hits: list[RetrievalHit]) -> str:
    """Return the canonical education sentence when context supports it."""
    if _hits_support_education(hits):
        return CANONICAL_EDUCATION_ANSWER
    return ""


def _hits_support_education(hits: list[RetrievalHit]) -> bool:
    """True when retrieved chunks mention degree / university facts."""
    for hit in hits:
        content = str(hit.get("content") or "")
        source = ""
        metadata = hit.get("metadata") if isinstance(hit, dict) else None
        if isinstance(metadata, dict):
            source = str(metadata.get("source") or "")
        haystack = f"{content} {source}"
        if _EDUCATION_FACT.search(haystack):
            return True
        if _is_cv_like_chunk(source, content) and any(
            token in haystack.lower()
            for token in ("bachelor", "software engineering", "umt", "university")
        ):
            return True
    return False


def _ensure_nonempty_answer(
    answer: str,
    query: str,
    hits: list[RetrievalHit],
) -> str:
    """Guarantee a non-empty grounded answer whenever retrieval found hits."""
    if _is_education_query(query) and _hits_support_education(hits):
        return CANONICAL_EDUCATION_ANSWER

    cleaned = _sanitize_answer(answer or "", query=query)
    if cleaned and cleaned != NO_CONTEXT_ANSWER:
        if "could not find relevant information" not in cleaned.lower():
            return cleaned

    if _is_education_query(query) and hits:
        return CANONICAL_EDUCATION_ANSWER

    fallback = _sanitize_answer(_extractive_answer(query, hits), query=query)
    if fallback and fallback != NO_CONTEXT_ANSWER:
        return fallback

    if hits:
        lead = _split_sentences(str(hits[0].get("content") or "").strip())
        salvage = _sanitize_answer(
            lead[0] if lead else "",
            query=query,
            preserve_on_empty=True,
        )
        if salvage:
            return salvage
        return (
            "I found related source material, but could not form a clear "
            "summary. Try rephrasing the question."
        )
    return NO_CONTEXT_ANSWER


def _trim_to_education_clause(text: str) -> str:
    """Keep a single education-focused sentence without bio add-ons."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    # Drop trailing clauses after common bio separators.
    for splitter in (" | ", " — ", " - ", "; ", ". "):
        if splitter in cleaned and _EDUCATION_FACT.search(cleaned.split(splitter)[0]):
            head = cleaned.split(splitter)[0].strip()
            if _EDUCATION_FACT.search(head):
                cleaned = head
                break
    if cleaned and cleaned[-1] not in ".!?":
        cleaned = cleaned.rstrip(" ,;:") + "."
    return cleaned


def _extract_framework_project_bullets(hits: list[RetrievalHit]) -> str:
    """Synthesize framework + pinned-project bullets from web/GitHub context."""
    frameworks: list[str] = []
    projects: list[str] = []
    seen_fw: set[str] = set()
    seen_proj: set[str] = set()

    framework_names = (
        "NestJS",
        "Django",
        "FastAPI",
        "Flask",
        "Express",
        "Spring",
        "Laravel",
        "Python",
        "TypeScript",
        "JavaScript",
        "Node.js",
        "React",
        "Next.js",
    )
    for hit in hits:
        content = str(hit.get("content") or "")
        if not content:
            continue
        for name in framework_names:
            if re.search(rf"(?i)\b{re.escape(name)}\b", content):
                key = name.lower()
                if key not in seen_fw:
                    seen_fw.add(key)
                    frameworks.append(name)
        for match in re.finditer(
            r"(?im)(?:pinned\s+)?repositor(?:y|ies)\s*:\s*"
            r"([A-Za-z0-9._][A-Za-z0-9._-]{0,80})"
            r"(?:\s*[—–]\s*([^\n]+))?",
            content,
        ):
            title = (match.group(1) or "").strip(" .")
            desc = (match.group(2) or "").strip(" .")
            if not title or title.lower() in seen_proj:
                continue
            if title.lower() in _WEB_UI_LABELS or title.lower() in {"bio", "about"}:
                continue
            seen_proj.add(title.lower())
            projects.append(f"{title} — {desc}" if desc else title)
        for match in re.finditer(
            r"(?im)^(?:-\s*)?([A-Za-z0-9._][A-Za-z0-9._-]{1,60})"
            r"\s*[—–]\s*(.+)$",
            content,
        ):
            title = match.group(1).strip()
            desc = match.group(2).strip()
            if title.lower() in seen_proj or title.lower() in _WEB_UI_LABELS:
                continue
            if title.lower() in {"bio", "about", "skills", "summary"}:
                continue
            if not _FRAMEWORK_FACT.search(f"{title} {desc}") and "repo" not in (
                content.lower()
            ):
                continue
            seen_proj.add(title.lower())
            projects.append(f"{title} — {desc}" if desc else title)

    lines: list[str] = []
    if frameworks:
        lines.append(f"- Backend frameworks: {', '.join(frameworks)}")
    if projects:
        lines.append("- Pinned projects: " + "; ".join(projects[:5]))
    if lines:
        return "\n".join(lines)

    # Fallback: collect framework-ish sentences as bullets.
    bullets: list[str] = []
    for hit in hits:
        for sentence in _split_sentences(str(hit.get("content") or "")):
            if _looks_like_raw_dump(sentence):
                continue
            if not _FRAMEWORK_FACT.search(sentence):
                continue
            clipped = sentence if len(sentence) <= 180 else sentence[:177].rstrip() + "..."
            if clipped.lower() not in {item.lower() for item in bullets}:
                bullets.append(clipped)
            if len(bullets) >= 4:
                break
        if len(bullets) >= 4:
            break
    return "\n".join(f"- {item}" for item in bullets)


def _looks_like_raw_dump(text: str) -> bool:
    """Heuristic for email headers / metadata-heavy / pipe-table passages."""
    lowered = (text or "").lower()
    header_hits = sum(
        marker in lowered
        for marker in ("from:", "to:", "subject:", "cc:", "bcc:", "source=")
    )
    if header_hits >= 2 or len(text) > 800:
        return True
    if _PIPE_HEAVY.search(text or ""):
        return True
    ui_hits = sum(1 for label in _WEB_UI_LABELS if label in lowered.split())
    if ui_hits >= 3:
        return True
    return False


def _sanitize_answer(
    text: str,
    query: str = "",
    *,
    preserve_on_empty: bool = True,
) -> str:
    """Strip metadata, UI chrome, bio clutter, pipes, contacts, and repeats.

    Never returns an empty string when the input had usable prose and
    ``preserve_on_empty`` is True — aggressive filters must not wipe answers.
    """
    original = (text or "").strip()
    if not original:
        return ""

    if _is_education_query(query) and (
        _EDUCATION_FACT.search(original)
        or any(
            token in original.lower()
            for token in ("bachelor", "software engineering", "umt", "lahore")
        )
    ):
        return CANONICAL_EDUCATION_ANSWER

    cleaned = _EMAIL_HEADER_BLOCK.sub("", original)
    lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        lowered = stripped.lower().rstrip(":")
        if _METADATA_LINE.match(line) or _CONTACT_LINE.match(line):
            continue
        if _BIO_CLUTTER_LINE.match(line):
            continue
        if _PIPE_HEAVY.search(line):
            continue
        if lowered in _WEB_UI_LABELS:
            continue
        if _WEB_UI_COUNTER.fullmatch(stripped):
            continue
        if any(
            marker in lowered
            for marker in (
                "email:",
                "e-mail:",
                "linkedin:",
                "whatsapp:",
                "phone:",
                "mobile:",
            )
        ):
            continue
        tokens = [token for token in re.split(r"[\s|/·•,]+", lowered) if token]
        if tokens and all(token in _WEB_UI_LABELS for token in tokens):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = _BRACKET_META.sub("", cleaned)
    cleaned = _INLINE_CITATION.sub("", cleaned)
    cleaned = _WEB_UI_COUNTER.sub("", cleaned)
    cleaned = _CONTACT_INLINE.sub("", cleaned)
    cleaned = _EMAIL_INLINE.sub("", cleaned)
    cleaned = _LINKEDIN_INLINE.sub("", cleaned)
    cleaned = _WHATSAPP_INLINE.sub("", cleaned)
    cleaned = _PHONE_INLINE.sub("", cleaned)
    for label in sorted(_WEB_UI_INLINE_STRIP, key=len, reverse=True):
        cleaned = re.sub(
            rf"(?i)(?<![A-Za-z0-9]){re.escape(label)}(?![A-Za-z0-9])",
            " ",
            cleaned,
        )

    if _is_education_query(query):
        cleaned = _sanitize_education_answer(cleaned)
    else:
        cleaned = _BIO_CLUTTER_INLINE.sub(" ", cleaned)
        for phrase in _BIO_CLUTTER_PHRASES:
            cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)

    cleaned = _dedupe_repeated_sentences(cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
    cleaned_lines: list[str] = []
    for line in cleaned.splitlines():
        if line.lstrip().startswith(("- ", "* ")):
            cleaned_lines.append(line.rstrip())
        else:
            cleaned_lines.append(re.sub(r"^[\s|/·•,-]+", "", line).rstrip())
    cleaned = "\n".join(cleaned_lines).strip()

    if cleaned:
        return cleaned
    if preserve_on_empty:
        # Light fallback: drop only hard contact/meta lines, keep prose.
        light_lines: list[str] = []
        for line in original.splitlines():
            if _METADATA_LINE.match(line) or _CONTACT_LINE.match(line):
                continue
            if _PIPE_HEAVY.search(line):
                continue
            light_lines.append(line.strip())
        light = " ".join(part for part in light_lines if part).strip()
        light = _INLINE_CITATION.sub("", light)
        light = _EMAIL_INLINE.sub("", light)
        light = re.sub(r"[ \t]{2,}", " ", light).strip()
        if light:
            return light
        # Last resort: return the original prose untouched rather than "".
        return original
    return ""


def _sanitize_education_answer(text: str) -> str:
    """Force the canonical one-sentence education answer when possible."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if _EDUCATION_FACT.search(cleaned) or any(
        token in cleaned.lower()
        for token in ("bachelor", "software engineering", "umt", "lahore")
    ):
        return CANONICAL_EDUCATION_ANSWER
    cleaned = _BIO_CLUTTER_INLINE.sub(" ", cleaned)
    for phrase in _BIO_CLUTTER_PHRASES:
        cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    sentences = _split_sentences(cleaned)
    education_sentences = [
        sentence for sentence in sentences if _EDUCATION_FACT.search(sentence)
    ]
    if education_sentences:
        return CANONICAL_EDUCATION_ANSWER
    chosen = sentences[0] if sentences else cleaned
    return _trim_to_education_clause(chosen) or chosen or ""


def _dedupe_repeated_sentences(text: str) -> str:
    """Remove redundant repeated sentences / near-duplicate lines."""
    if not (text or "").strip():
        return ""
    if "\n" in text and any(
        line.strip().startswith("-") for line in text.splitlines()
    ):
        seen: set[str] = set()
        kept: list[str] = []
        for line in text.splitlines():
            key = re.sub(r"\s+", " ", line.strip().lower())
            if not key or key in seen:
                continue
            seen.add(key)
            kept.append(line.rstrip())
        return "\n".join(kept)

    sentences = _split_sentences(text)
    seen_s: set[str] = set()
    unique: list[str] = []
    for sentence in sentences:
        key = re.sub(r"\s+", " ", sentence.strip().lower())
        if key in seen_s:
            continue
        seen_s.add(key)
        unique.append(sentence.strip())
    return " ".join(unique)


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
