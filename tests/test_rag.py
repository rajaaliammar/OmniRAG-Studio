"""Tests for the RAG pipeline."""

import pytest

from backend.rag.prompts import get_qa_prompt


def test_qa_prompt_contains_context_placeholder() -> None:
    """Default QA prompt must include a context slot."""
    prompt = get_qa_prompt()
    assert "{context}" in prompt
    assert "{question}" in prompt


def test_rag_chain_placeholder() -> None:
    """RAG chain builder should raise until implemented."""
    from backend.rag.chains import build_rag_chain

    with pytest.raises(NotImplementedError):
        build_rag_chain()
