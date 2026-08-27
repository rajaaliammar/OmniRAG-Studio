"""Retriever over the ChromaDB collection."""

from typing import Any


def get_retriever(k: int = 4) -> Any:
    """Build a similarity retriever over the default collection.

    Args:
        k: Number of chunks to return per query.

    Returns:
        A LangChain-compatible retriever.

    Raises:
        NotImplementedError: Until retrieval is implemented.
    """
    raise NotImplementedError("Vector retriever is not implemented yet.")
