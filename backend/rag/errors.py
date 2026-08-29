"""Domain exceptions for the RAG pipeline."""


class RagError(RuntimeError):
    """Raised when retrieval-augmented generation fails."""
