"""Tests for the ChromaDB vector store and embeddings helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from langchain_core.documents import Document

from backend.config import Settings
from backend.vectorstore.chroma_db import (
    add_documents_to_vectorstore,
    collection_exists,
    delete_collection,
    get_or_create_collection,
    list_collections,
    normalize_collection_name,
    reset_chroma_client,
)
from backend.vectorstore.embeddings import embed_documents, embed_query, get_embeddings
from backend.vectorstore.errors import VectorStoreError
from backend.vectorstore.retriever import similarity_search


def _hash_embedding(text: str, dims: int = 8) -> list[float]:
    """Deterministic stand-in for OpenAI embeddings."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [byte / 255.0 for byte in digest[:dims]]


@pytest.fixture
def chroma_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point Chroma at a temp directory and stub local embeddings."""
    reset_chroma_client()
    monkeypatch.setattr(
        "backend.vectorstore.chroma_db.get_settings",
        lambda: Settings(
            openai_api_key="",
            chroma_db_path=str(tmp_path / "chroma"),
            embedding_provider="huggingface",
        ),
    )
    monkeypatch.setattr(
        "backend.vectorstore.embeddings.embed_documents",
        lambda texts, batch_size=None: [_hash_embedding(text) for text in texts],
    )
    monkeypatch.setattr(
        "backend.vectorstore.chroma_db.embed_documents",
        lambda texts, batch_size=None: [_hash_embedding(text) for text in texts],
    )
    monkeypatch.setattr(
        "backend.vectorstore.retriever.embed_query",
        lambda text: _hash_embedding(text),
    )
    yield tmp_path
    reset_chroma_client()


def test_get_embeddings_defaults_to_huggingface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default provider should construct HuggingFaceEmbeddings without an API key."""
    from backend.vectorstore import embeddings as embeddings_mod

    fake_client = object()
    captured: dict[str, object] = {}

    def _fake_hf(**kwargs: object) -> object:
        captured.update(kwargs)
        return fake_client

    embeddings_mod.reset_embedding_clients()
    monkeypatch.setattr(
        "backend.vectorstore.embeddings.get_settings",
        lambda: Settings(openai_api_key="", embedding_provider="huggingface"),
    )
    monkeypatch.setattr(
        "backend.vectorstore.embeddings.HuggingFaceEmbeddings",
        _fake_hf,
    )
    client = get_embeddings()
    assert client is fake_client
    assert captured["model_name"] == "all-MiniLM-L6-v2"
    assert captured["model_kwargs"] == {"device": "cpu"}


def test_huggingface_remaps_openai_model_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy OpenAI model names should not be sent to sentence-transformers."""
    from backend.vectorstore import embeddings as embeddings_mod

    captured: dict[str, object] = {}

    def _fake_hf(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    embeddings_mod.reset_embedding_clients()
    monkeypatch.setattr(
        "backend.vectorstore.embeddings.get_settings",
        lambda: Settings(
            openai_api_key="",
            embedding_provider="huggingface",
            embedding_model="text-embedding-3-small",
        ),
    )
    monkeypatch.setattr(
        "backend.vectorstore.embeddings.HuggingFaceEmbeddings",
        _fake_hf,
    )
    get_embeddings()
    assert captured["model_name"] == "all-MiniLM-L6-v2"


def test_get_embeddings_returns_cached_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The HuggingFace client must be constructed only once per model."""
    from backend.vectorstore import embeddings as embeddings_mod

    calls = {"n": 0}
    fake_client = object()

    def _fake_hf(**kwargs: object) -> object:
        calls["n"] += 1
        return fake_client

    embeddings_mod.reset_embedding_clients()
    monkeypatch.setattr(
        "backend.vectorstore.embeddings.get_settings",
        lambda: Settings(openai_api_key="", embedding_provider="huggingface"),
    )
    monkeypatch.setattr(
        "backend.vectorstore.embeddings.HuggingFaceEmbeddings",
        _fake_hf,
    )
    first = get_embeddings()
    second = get_embeddings()
    assert first is second is fake_client
    assert calls["n"] == 1


def test_huggingface_class_unbound_until_first_load() -> None:
    """Importing embeddings.py must not load sentence-transformers / torch."""
    from backend.vectorstore import embeddings as embeddings_mod

    embeddings_mod.reset_embedding_clients()
    embeddings_mod.HuggingFaceEmbeddings = None
    assert embeddings_mod.HuggingFaceEmbeddings is None


def test_get_embeddings_openai_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI provider should fail without a key."""
    monkeypatch.setattr(
        "backend.vectorstore.embeddings.get_settings",
        lambda: Settings(openai_api_key="", embedding_provider="openai"),
    )
    with pytest.raises(VectorStoreError, match="OPENAI_API_KEY"):
        get_embeddings()


def test_embed_query_and_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single and batch helpers should call the embeddings client."""

    class _FakeEmbedder:
        def embed_query(self, text: str) -> list[float]:
            return [1.0, 2.0]

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[float(index), 0.5] for index, _ in enumerate(texts)]

    monkeypatch.setattr(
        "backend.vectorstore.embeddings.get_embeddings",
        lambda model=None: _FakeEmbedder(),
    )
    assert embed_query("hello") == [1.0, 2.0]
    assert embed_documents(["a", "b"]) == [[0.0, 0.5], [1.0, 0.5]]


def test_embed_query_rejects_empty() -> None:
    """Empty queries should not hit the embedding API."""
    with pytest.raises(VectorStoreError):
        embed_query("   ")


def test_normalize_collection_name_pads_short_values() -> None:
    """Chroma names must be at least three characters."""
    assert normalize_collection_name("ab") == "col_ab"


def test_add_list_search_and_delete(chroma_tmp: Path) -> None:
    """Documents should round-trip through Chroma with relevance scores."""
    docs = [
        Document(page_content="alpha widget", metadata={"source": "a.txt", "page": 1}),
        Document(page_content="beta gadget", metadata={"source": "b.txt", "page": 2}),
    ]
    stored = add_documents_to_vectorstore("phase3_test", docs)
    assert stored == 2
    assert "phase3_test" in list_collections()

    collection = get_or_create_collection("phase3_test")
    assert collection.count() == 2

    hits = similarity_search("alpha widget", "phase3_test", k=2)
    assert hits
    assert hits[0]["content"] == "alpha widget"
    assert hits[0]["metadata"]["source"] == "a.txt"
    assert hits[0]["metadata"]["page"] == 1
    assert hits[0]["score"] >= hits[-1]["score"]
    assert 0.0 <= hits[0]["score"] <= 1.0 + 1e-6

    tight = similarity_search(
        "alpha widget",
        "phase3_test",
        k=2,
        score_threshold=0.999,
    )
    assert all(hit["score"] >= 0.999 for hit in tight)

    delete_collection("phase3_test")
    assert "phase3_test" not in list_collections()


def test_collection_exists(chroma_tmp: Path) -> None:
    """collection_exists should distinguish missing vs created collections."""
    assert collection_exists("missing_col") is False
    get_or_create_collection("present_col")
    assert collection_exists("present_col") is True


def test_add_documents_rejects_empty(chroma_tmp: Path) -> None:
    """Indexing an empty payload should fail clearly."""
    with pytest.raises(VectorStoreError, match="No documents"):
        add_documents_to_vectorstore("empty_docs", [])


def test_similarity_search_empty_collection(chroma_tmp: Path) -> None:
    """An unused collection should return no hits."""
    get_or_create_collection("unused_col")
    assert similarity_search("anything", "unused_col") == []
