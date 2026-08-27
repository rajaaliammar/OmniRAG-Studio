"""Embedding model factory."""

from typing import Any


def get_embeddings() -> Any:
    """Return the configured embedding model client.

    Returns:
        An embeddings object compatible with LangChain / ChromaDB.

    Raises:
        NotImplementedError: Until embeddings are wired up.
    """
    raise NotImplementedError("Embedding model is not configured yet.")
