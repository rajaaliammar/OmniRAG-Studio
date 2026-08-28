"""Domain exceptions for the vector store layer."""


class VectorStoreError(RuntimeError):
    """Raised when embeddings or ChromaDB operations fail."""
