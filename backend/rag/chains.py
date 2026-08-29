"""LangChain RAG chain assembly (compatibility wrapper)."""

from backend.rag.chain import RagResult, answer_query, build_rag_chain

__all__ = ["RagResult", "answer_query", "build_rag_chain"]
