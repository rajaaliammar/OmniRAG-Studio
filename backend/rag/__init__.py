"""RAG pipeline (prompts, chain, citations, memory)."""

from backend.rag.chain import RagResult, answer_query, build_rag_chain
from backend.rag.citation import format_citations
from backend.rag.errors import RagError
from backend.rag.memory import ConversationMemory, get_memory, reset_memory
from backend.rag.prompts import get_qa_prompt

__all__ = [
    "ConversationMemory",
    "RagError",
    "RagResult",
    "answer_query",
    "build_rag_chain",
    "format_citations",
    "get_memory",
    "get_qa_prompt",
    "reset_memory",
]
