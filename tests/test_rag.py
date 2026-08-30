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
    assert citations[0] == {"source": "handbook.pdf", "page/row": "3"}
    assert citations[1] == {"source": "catalog.csv", "page/row": "1"}
    assert citations[2]["source"] == "https://example.com/docs"
    assert citations[2]["page/row"] == "https://example.com/docs"


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
        content = "The widget costs 9.99 [1]."

    class _FakeLLM:
        def invoke(self, messages: list[object]) -> _FakeMessage:
            assert messages
            return _FakeMessage()

    monkeypatch.setattr("backend.rag.chain._get_chat_model", lambda: _FakeLLM())
    result = answer_query("How much is the widget?", "local_test", session_id="shop")
    assert "9.99" in result.answer
    assert result.citations == [{"source": "catalog.csv", "page/row": "0"}]
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
    assert "[1]" in result.answer
    assert result.citations == [{"source": "catalog.csv", "page/row": "0"}]


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
    assert "User: hello" in memory.format_for_prompt("abc")
    assert memory.clear("abc") is True
    assert memory.history("abc") == []
    assert memory.clear("abc") is False


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
            answer="Grounded answer [1].",
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
    assert body["answer"] == "Grounded answer [1]."
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
