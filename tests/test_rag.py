"""Tests for the RAG pipeline, memory, and chat API."""

from __future__ import annotations

import pytest
from langchain_core.documents import Document

from backend.rag.chain import (
    NO_CONTEXT_ANSWER,
    RagResult,
    answer_query,
    build_rag_chain,
    reset_llm_client,
)
from backend.rag.citation import format_citations
from backend.rag.memory import get_memory, reset_memory
from backend.rag.prompts import get_qa_prompt


@pytest.fixture(autouse=True)
def _clean_memory() -> None:
    """Isolate conversational memory between tests."""
    reset_memory()
    reset_llm_client()
    yield
    reset_memory()
    reset_llm_client()


@pytest.fixture
def existing_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip Chroma lookups in HTTP chat tests that assume a populated store."""
    monkeypatch.setattr(
        "backend.api.v1.chat.collection_exists",
        lambda name: True,
    )


def test_qa_prompt_contains_context_placeholder() -> None:
    """Default QA prompt must include a context slot."""
    prompt = get_qa_prompt()
    assert "{context}" in prompt
    assert "{question}" in prompt
    assert "contact blocks" in prompt.lower() or "clean" in prompt.lower()


def test_format_citations_from_hits_and_documents() -> None:
    """Citations should expose source plus page, row, or URL."""
    hits = [
        {
            "content": "hello",
            "metadata": {"source": "handbook.pdf", "page": 3},
            "score": 0.9,
        },
        {
            "content": "row",
            "metadata": {"source": "catalog.csv", "row_index": 1},
            "score": 0.8,
        },
        Document(
            page_content="web",
            metadata={"source": "https://example.com/docs", "title": "Docs"},
        ),
    ]
    citations = format_citations(hits)
    assert citations[0]["source"] == "handbook.pdf"
    assert citations[0]["page/row"] == "3"
    assert citations[0]["score"] == 0.9
    assert citations[0]["snippet"] == "hello"
    assert citations[1]["source"] == "catalog.csv"
    assert citations[1]["page/row"] == "1"
    assert citations[1]["score"] == 0.8
    assert citations[2]["source"] == "https://example.com/docs"
    assert citations[2]["page/row"] == "https://example.com/docs"
    assert citations[2]["snippet"] == "web"


def test_answer_query_no_hits_does_not_call_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty retrieval must return the fallback and skip generation."""
    monkeypatch.setattr("backend.rag.chain.similarity_search", lambda *a, **k: [])
    called = {"llm": False}

    def _boom() -> None:
        called["llm"] = True
        raise AssertionError("LLM should not run without context")

    monkeypatch.setattr("backend.rag.chain._get_chat_model", _boom)
    result = answer_query("What is OmniRAG?", "local_test", session_id="s1")
    assert result.answer == NO_CONTEXT_ANSWER
    assert result.citations == []
    assert result.session_id == "s1"
    assert called["llm"] is False
    history = get_memory().history("s1")
    assert len(history) == 2
    assert history[0].role == "user"


def test_answer_query_uses_llm_and_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hits should be passed to the LLM and returned as citations."""
    hits = [
        {
            "content": "The widget costs 9.99.",
            "metadata": {"source": "catalog.csv", "row_index": 0},
            "score": 0.91,
        }
    ]
    monkeypatch.setattr(
        "backend.rag.chain.similarity_search",
        lambda *a, **k: hits,
    )

    class _FakeMessage:
        content = "The widget costs 9.99."

    class _FakeLLM:
        def invoke(self, messages: list[object]) -> _FakeMessage:
            assert messages
            return _FakeMessage()

    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: _FakeLLM())
    result = answer_query("How much is the widget?", "local_test", session_id="shop")
    assert "9.99" in result.answer
    assert "[1]" not in result.answer
    assert result.citations[0]["source"] == "catalog.csv"
    assert result.citations[0]["page/row"] == "0"
    assert result.citations[0]["score"] == 0.91
    assert "9.99" in result.citations[0]["snippet"]
    assert result.session_id == "shop"


def test_answer_query_falls_back_on_openai_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 429 / insufficient_quota must yield extractive sentences, not RagError."""
    hits = [
        {
            "content": "The widget costs 9.99. Shipping is free over 50.",
            "metadata": {"source": "catalog.csv", "row_index": 0},
            "score": 0.91,
        }
    ]
    monkeypatch.setattr(
        "backend.rag.chain.similarity_search",
        lambda *a, **k: hits,
    )

    class RateLimitError(Exception):
        status_code = 429

        def __str__(self) -> str:
            return "Error code: 429 - insufficient_quota"

    class _FakeLLM:
        def invoke(self, messages: list[object]) -> None:
            raise RateLimitError()

    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: _FakeLLM())
    result = answer_query("How much is the widget?", "local_test", session_id="quota")
    assert "9.99" in result.answer
    assert "[1]" not in result.answer
    assert result.citations[0]["source"] == "catalog.csv"
    assert result.citations[0]["page/row"] == "0"
    assert result.citations[0]["score"] == 0.91


def test_chat_query_returns_200_when_llm_quota_exceeded(
    monkeypatch: pytest.MonkeyPatch,
    existing_collection: None,
) -> None:
    """POST /api/v1/chat/query stays 200 when the chain uses extractive fallback."""
    from fastapi.testclient import TestClient

    from backend.main import app

    hits = [
        {
            "content": "OmniRAG Studio indexes PDF, CSV, and web pages.",
            "metadata": {"source": "readme.md", "page": 1},
            "score": 0.8,
        }
    ]
    monkeypatch.setattr(
        "backend.rag.chain.similarity_search",
        lambda *a, **k: hits,
    )

    class RateLimitError(Exception):
        status_code = 429

        def __str__(self) -> str:
            return "insufficient_quota"

    class _FakeLLM:
        def invoke(self, messages: list[object]) -> None:
            raise RateLimitError()

    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: _FakeLLM())
    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "What does OmniRAG index?",
            "collection_name": "local_test",
            "session_id": "quota-api",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"]
    assert "PDF" in body["answer"] or "OmniRAG" in body["answer"]
    assert body["citations"][0]["source"] == "readme.md"
    assert body["citations"][0]["page/row"] == "1"


def test_build_rag_chain_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_rag_chain should return a callable around answer_query."""
    monkeypatch.setattr("backend.rag.chain.similarity_search", lambda *a, **k: [])
    chain = build_rag_chain()
    result = chain("anything", "local_test", "sid")
    assert isinstance(result, RagResult)
    assert result.citations == []


def test_memory_append_and_clear() -> None:
    """Session memory should store turns and clear by session id."""
    memory = get_memory()
    memory.append("abc", "user", "hello")
    memory.append("abc", "assistant", "hi")
    assert len(memory.history("abc")) == 2
    formatted = memory.format_for_prompt("abc")
    assert "User (turn 1): hello" in formatted
    assert "Assistant: hi" in formatted
    assert memory.clear("abc") is True
    assert memory.history("abc") == []
    assert memory.clear("abc") is False


def test_history_followup_uses_session_not_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Meta questions about prior turns must not dump retrieved documents."""
    memory = get_memory()
    memory.append("hist-1", "user", "What is my BS degree?")
    memory.append(
        "hist-1",
        "assistant",
        "- Degree: BS Computer Science\n- Institute: Example University",
    )

    def _unexpected_search(*_args: object, **_kwargs: object) -> list:
        raise AssertionError("History follow-ups must skip similarity search")

    monkeypatch.setattr("backend.rag.chain.similarity_search", _unexpected_search)
    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: None)

    result = answer_query(
        "Mera pehla question kya tha?",
        "local_test",
        session_id="hist-1",
    )
    assert "What is my BS degree?" in result.answer
    assert result.citations == []
    assert "source=" not in result.answer.lower()
    assert len(memory.history("hist-1")) == 4


def test_sanitize_answer_strips_metadata_dumps() -> None:
    """Answer guardrails should remove raw metadata, pipes, UI, and [n] tags."""
    from backend.rag.chain import _sanitize_answer

    raw = (
        "From: hr@example.com\n"
        "To: candidate@example.com\n"
        "Subject: Resume dump\n\n"
        "source=resume.pdf page=1\n"
        "Follow\nOverview\nRepositories\nPackages\nStars\n"
        "Email: ali@example.com\n"
        "LinkedIn: https://linkedin.com/in/ali\n"
        "WhatsApp: +92 300 1234567\n"
        "Name | Email | Phone | City | Extra\n"
        "Ali Ammar holds a Bachelor of Science in Software Engineering [1]."
    )
    cleaned = _sanitize_answer(raw)
    assert "From:" not in cleaned
    assert "source=" not in cleaned.lower()
    assert "|" not in cleaned
    assert "[1]" not in cleaned
    assert "Follow" not in cleaned
    assert "Overview" not in cleaned
    assert "Repositories" not in cleaned
    assert "ali@example.com" not in cleaned.lower()
    assert "linkedin.com" not in cleaned.lower()
    assert "whatsapp" not in cleaned.lower()
    assert "Bachelor of Science" in cleaned


def test_sanitize_education_strips_bio_clutter() -> None:
    """Education answers must be the canonical one-sentence qualification."""
    from backend.rag.chain import CANONICAL_EDUCATION_ANSWER, _sanitize_answer

    raw = (
        "Ali Ammar holds a Bachelor of Science in Software Engineering from "
        "University of Management and Technology (UMT), Lahore. "
        "He builds AI agents with long-term memory. Skills: Python, NestJS. "
        "Tech stack: FastAPI."
    )
    cleaned = _sanitize_answer(
        raw,
        query="Ali Ammar ki qualification kya hai?",
    )
    assert cleaned == CANONICAL_EDUCATION_ANSWER
    assert "AI agents" not in cleaned
    assert "Skills" not in cleaned
    assert "NestJS" not in cleaned


def test_sanitize_never_returns_empty_for_valid_prose() -> None:
    """Aggressive filters must not wipe a valid answer to an empty string."""
    from backend.rag.chain import _sanitize_answer

    raw = (
        "Follow Overview Repositories Packages "
        "Ali Ammar's repos include OmniRAG-Studio and portfolio-site."
    )
    cleaned = _sanitize_answer(raw, query="What are the GitHub projects?")
    assert cleaned.strip()
    assert "OmniRAG-Studio" in cleaned


def test_ensure_nonempty_education_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qualification queries must return the exact canonical education sentence."""
    from backend.rag.chain import CANONICAL_EDUCATION_ANSWER

    hits = [
        {
            "content": (
                "Email: ali@example.com\nSkills: AI agents, long-term memory\n"
                "Bachelor of Science in Software Engineering, UMT Lahore"
            ),
            "metadata": {"source": "AliAmmar_CV.pdf", "page": 1},
            "score": 0.4,
        }
    ]
    monkeypatch.setattr(
        "backend.rag.chain.similarity_search",
        lambda *a, **k: hits,
    )
    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: None)
    result = answer_query(
        "Ali Ammar ki qualification kya hai?",
        "local_test",
        session_id="edu-canonical-1",
    )
    assert result.answer == CANONICAL_EDUCATION_ANSWER
    assert result.citations
    assert result.citations[0]["source"] == "AliAmmar_CV.pdf"


def test_sanitize_answer_strips_inline_web_ui_noise() -> None:
    """Glued GitHub nav chrome should be removed from synthesized answers."""
    from backend.rag.chain import _sanitize_answer

    raw = (
        "Follow Overview Repositories Packages Stars "
        "Ali Ammar's repos include OmniRAG-Studio and portfolio-site."
    )
    cleaned = _sanitize_answer(raw)
    assert "Follow" not in cleaned
    assert "Overview" not in cleaned
    assert "Repositories" not in cleaned
    assert "Packages" not in cleaned
    assert "OmniRAG-Studio" in cleaned


def test_extractive_framework_query_returns_bullets() -> None:
    """Framework/project questions should synthesize clean bullet lists."""
    from backend.rag.chain import _extractive_answer, _sanitize_answer

    hits = [
        {
            "content": (
                "Pinned repository: OmniRAG-Studio — Multi-source RAG chatbot "
                "(Language: Python)\n"
                "Pinned repository: api-gateway — NestJS backend service\n"
                "Bio: Building AI agents with long-term memory"
            ),
            "metadata": {"source": "https://github.com/rajaaliammar"},
            "score": 0.4,
        }
    ]
    answer = _sanitize_answer(
        _extractive_answer("What backend frameworks and pinned projects?", hits),
        query="What backend frameworks and pinned projects?",
    )
    assert "-" in answer
    assert "Python" in answer or "NestJS" in answer
    assert "OmniRAG-Studio" in answer
    assert "AI agents" not in answer
    assert "React" not in answer


def test_ood_query_never_dumps_bio_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Out-of-domain personal asks must use the exact missing-context sentence."""
    from backend.rag.chain import _ood_missing_answer

    hits = [
        {
            "content": (
                "Ali Ammar builds AI agents with long-term memory. "
                "Skills: Python, NestJS. Pinned repository: OmniRAG-Studio"
            ),
            "metadata": {"source": "resume.pdf"},
            "score": 0.4,
        }
    ]
    monkeypatch.setattr(
        "backend.rag.chain.similarity_search",
        lambda *a, **k: hits,
    )
    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: None)
    result = answer_query(
        "What is Ali Ammar's favorite movie?",
        "local_test",
        session_id="ood-movie-1",
    )
    assert result.answer == _ood_missing_answer("favorite movie")
    assert "AI agents" not in result.answer
    assert "Skills" not in result.answer
    assert "OmniRAG-Studio" not in result.answer
    assert "long-term memory" not in result.answer.lower()


def test_backend_stack_query_is_categorized_and_strips_frontend() -> None:
    """Backend stack answers must use strict categories without frontend tech."""
    from backend.rag.chain import (
        CANONICAL_BACKEND_STACK_ANSWER,
        _extractive_answer,
        _sanitize_answer,
    )

    hits = [
        {
            "content": (
                "Stack: Python, TypeScript, NestJS, FastAPI, PostgreSQL, Qdrant, "
                "React, Next.js, HTML, CSS"
            ),
            "metadata": {"source": "notes.md"},
            "score": 0.5,
        }
    ]
    answer = _sanitize_answer(
        _extractive_answer("What is the backend tech stack?", hits),
        query="What is the backend tech stack?",
    )
    assert answer == CANONICAL_BACKEND_STACK_ANSWER
    assert "Programming Languages: Python, TypeScript" in answer
    assert "Databases: PostgreSQL, Qdrant" in answer
    assert "Frameworks: NestJS, FastAPI" in answer
    assert "React" not in answer
    assert "Next.js" not in answer
    assert "HTML" not in answer


def test_agent_skill_query_returns_two_sentence_mapping() -> None:
    """Agent/skill evaluation must return a non-empty two-sentence conclusion."""
    from backend.rag.chain import CANONICAL_AGENT_SKILL_ANSWER, _extractive_answer

    hits = [
        {
            "content": "BS Software Engineering; Python and TypeScript experience",
            "metadata": {"source": "cv.pdf"},
            "score": 0.4,
        }
    ]
    answer = _extractive_answer(
        "Is he suitable for building AI agents based on his skills?",
        hits,
    )
    assert answer == CANONICAL_AGENT_SKILL_ANSWER
    assert answer.count(".") >= 2
    assert "Software Engineering" in answer
    assert "Python" in answer and "TypeScript" in answer


def test_empty_llm_synthesis_falls_back_to_intent_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty LLM output must never reach the UI; intent fallback fills the gap."""
    hits = [
        {
            "content": "Ali Ammar holds a BS in Software Engineering from UMT Lahore.",
            "metadata": {"source": "cv.pdf", "page": 1},
            "score": 0.4,
        }
    ]
    monkeypatch.setattr(
        "backend.rag.chain.similarity_search",
        lambda *a, **k: hits,
    )
    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: None)
    monkeypatch.setattr(
        "backend.rag.chain._extractive_answer",
        lambda *a, **k: "",
    )
    result = answer_query(
        "Ali Ammar ki qualification kya hai?",
        "local_test",
        session_id="empty-synth-1",
    )
    assert result.answer.strip()
    assert "Software Engineering" in result.answer or "UMT" in result.answer


def test_grounded_prompt_forbids_raw_dumps() -> None:
    """System prompt must require synthesis instead of chunk dumping."""
    from backend.rag.prompts import GROUNDED_SYSTEM_PROMPT, build_grounded_user_prompt

    assert "contact blocks" in GROUNDED_SYSTEM_PROMPT.lower()
    assert "LinkedIn" in GROUNDED_SYSTEM_PROMPT
    assert "WhatsApp" in GROUNDED_SYSTEM_PROMPT
    assert "GitHub" in GROUNDED_SYSTEM_PROMPT
    assert "Bachelor of Science in Software Engineering" in GROUNDED_SYSTEM_PROMPT
    assert "ONLY what is explicitly asked" in GROUNDED_SYSTEM_PROMPT
    assert "University of Management and Technology (UMT), Lahore" in GROUNDED_SYSTEM_PROMPT
    assert "bulleted list" in GROUNDED_SYSTEM_PROMPT.lower() or "BACKEND STACK" in GROUNDED_SYSTEM_PROMPT
    assert "MULTI-HOP" in GROUNDED_SYSTEM_PROMPT
    assert "HYBRID" in GROUNDED_SYSTEM_PROMPT
    assert "does not contain information about" in GROUNDED_SYSTEM_PROMPT
    assert "NEVER dump raw bio" in GROUNDED_SYSTEM_PROMPT
    assert "Programming Languages: Python, TypeScript" in GROUNDED_SYSTEM_PROMPT
    assert "React" in GROUNDED_SYSTEM_PROMPT and "Strip" in GROUNDED_SYSTEM_PROMPT
    history_prompt = build_grounded_user_prompt(
        "Mera pehla question kya tha?",
        context="Passage 1 (source=resume.pdf):\nraw email body",
        history="User (turn 1): What is my degree?\nAssistant: BS CS",
        history_only=True,
    )
    assert "CONVERSATION HISTORY" in history_prompt
    assert "not used" in history_prompt
    normal_prompt = build_grounded_user_prompt(
        "GitHub repos?",
        context="Repository: OmniRAG-Studio",
        history_only=False,
    )
    assert "does not contain information about" in normal_prompt.lower()
    assert "ONE sentence" in normal_prompt or "qualification" in normal_prompt.lower()
    assert "multi-hop" in normal_prompt.lower() or "partial" in normal_prompt.lower()
    assert "NestJS, FastAPI" in normal_prompt or "backend stack" in normal_prompt.lower()


def test_rerank_prefers_github_url_over_cv() -> None:
    """GitHub queries must prioritize ingested URL context over CV chunks."""
    from backend.rag.chain import _rerank_and_filter

    hits = [
        {
            "content": (
                "Email: ali@example.com\nLinkedIn: linkedin.com/in/ali\n"
                "Internship at Acme Corp building internal tools"
            ),
            "metadata": {"source": "resume.pdf"},
            "score": 0.55,
        },
        {
            "content": (
                "Pinned repository: OmniRAG-Studio — Multi-source RAG chatbot "
                "(Language: Python)"
            ),
            "metadata": {"source": "https://github.com/rajaaliammar"},
            "score": 0.28,
        },
    ]
    filtered = _rerank_and_filter(
        "What are Ali Ammar's GitHub repositories?",
        hits,
        top_k=2,
        min_score=0.0,
        absolute_floor=0.10,
        relative_floor=0.05,
    )
    assert filtered
    assert filtered[0]["metadata"]["source"].startswith("https://github.com")
    assert all(
        "resume.pdf" not in str(hit["metadata"].get("source", ""))
        for hit in filtered
    )


def test_rerank_prefers_topical_chunks() -> None:
    """GitHub queries should keep repo chunks over weak CV matches."""
    from backend.rag.chain import _rerank_and_filter

    hits = [
        {
            "content": "Ali Ammar, phone 0300-0000000, BS Software Engineering UMT",
            "metadata": {"source": "resume.pdf"},
            "score": 0.55,
        },
        {
            "content": "GitHub repositories: OmniRAG-Studio and portfolio apps",
            "metadata": {"source": "github_profile.md"},
            "score": 0.48,
        },
    ]
    filtered = _rerank_and_filter(
        "What are Ali Ammar's GitHub repositories?",
        hits,
        top_k=2,
        min_score=0.0,
        absolute_floor=0.10,
        relative_floor=0.05,
    )
    assert filtered
    assert filtered[0]["metadata"]["source"] == "github_profile.md"


def test_rerank_keeps_best_hit_when_scores_are_soft() -> None:
    """Soft thresholds must still return the strongest available chunk."""
    from backend.rag.chain import _rerank_and_filter

    hits = [
        {
            "content": "Bachelor of Science in Software Engineering from UMT Lahore",
            "metadata": {"source": "cv.pdf"},
            "score": 0.12,
        }
    ]
    filtered = _rerank_and_filter(
        "Ali Ammar ki qualification kya hai?",
        hits,
        top_k=2,
        min_score=0.0,
        absolute_floor=0.10,
        relative_floor=0.05,
    )
    assert len(filtered) == 1
    assert filtered[0]["metadata"]["source"] == "cv.pdf"


def test_rerank_accepts_mid_confidence_chunks() -> None:
    """Chunks at >= 10% cosine relevance must enter the synthesis context."""
    from backend.rag.chain import _rerank_and_filter

    hits = [
        {
            "content": "OmniRAG-Studio is a multi-source RAG chatbot on GitHub",
            "metadata": {"source": "github.md"},
            "score": 0.11,
        },
        {
            "content": "Unrelated gardening tips about tomatoes",
            "metadata": {"source": "garden.md"},
            "score": 0.04,
        },
    ]
    filtered = _rerank_and_filter(
        "GitHub repositories for OmniRAG",
        hits,
        top_k=4,
        min_score=0.0,
        absolute_floor=0.10,
        relative_floor=0.05,
    )
    sources = [hit["metadata"]["source"] for hit in filtered]
    assert "github.md" in sources
    assert "garden.md" not in sources


def test_answer_query_synthesizes_when_hits_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-empty retrieval must never return the empty-context fallback."""
    hits = [
        {
            "content": "Ali Ammar holds a BS in Software Engineering from UMT Lahore.",
            "metadata": {"source": "cv.pdf", "page": 1},
            "score": 0.31,
        }
    ]
    monkeypatch.setattr(
        "backend.rag.chain.similarity_search",
        lambda *a, **k: hits,
    )
    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: None)
    result = answer_query(
        "Ali Ammar ki qualification kya hai?",
        "local_test",
        session_id="synth-1",
    )
    assert result.citations
    assert result.answer != NO_CONTEXT_ANSWER
    assert "could not find" not in result.answer.lower()
    assert result.answer.strip()
    assert "UMT" in result.answer or "Software Engineering" in result.answer
    from backend.rag.chain import CANONICAL_EDUCATION_ANSWER

    assert result.answer == CANONICAL_EDUCATION_ANSWER


def test_chat_query_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    existing_collection: None,
) -> None:
    """POST /api/v1/chat/query should return answer, citations, session_id."""
    from fastapi.testclient import TestClient

    from backend.main import app

    monkeypatch.setattr(
        "backend.api.v1.chat.answer_query",
        lambda query, collection, session_id=None: RagResult(
            answer="Grounded answer.",
            citations=[{"source": "notes.pdf", "page/row": "2"}],
            session_id=session_id or "generated",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "What is in the notes?",
            "collection_name": "local_test",
            "session_id": "sess-1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "Grounded answer."
    assert body["session_id"] == "sess-1"
    assert body["citations"][0]["source"] == "notes.pdf"
    assert body["citations"][0]["page/row"] == "2"


def test_chat_clear_endpoint() -> None:
    """POST /api/v1/chat/clear should drop session memory."""
    from fastapi.testclient import TestClient

    from backend.main import app

    get_memory().append("sess-9", "user", "hello")
    client = TestClient(app)
    response = client.post("/api/v1/chat/clear", json={"session_id": "sess-9"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "sess-9"
    assert body["cleared"] is True
    assert get_memory().history("sess-9") == []


def test_chat_query_rejects_empty_query() -> None:
    """Empty queries should be rejected with 422."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/query",
        json={"query": "", "collection_name": "local_test"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]


def test_chat_query_rejects_whitespace_query() -> None:
    """Whitespace-only queries should be rejected with 422."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/query",
        json={"query": "   ", "collection_name": "local_test"},
    )
    assert response.status_code == 422


def test_chat_query_missing_collection_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown collections should return HTTP 404 instead of empty answers."""
    from fastapi.testclient import TestClient

    from backend.main import app

    monkeypatch.setattr(
        "backend.api.v1.chat.collection_exists",
        lambda name: False,
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "What is in the notes?",
            "collection_name": "does_not_exist",
        },
    )
    assert response.status_code == 404
    detail = str(response.json()["detail"]).lower()
    assert "not found" in detail
    assert "ingest" in detail


def test_chat_clear_rejects_blank_session() -> None:
    """Clearing memory requires a non-empty session_id."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post("/api/v1/chat/clear", json={"session_id": "   "})
    assert response.status_code == 422
