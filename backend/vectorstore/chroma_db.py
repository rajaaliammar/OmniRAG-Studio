"""ChromaDB client and collection helpers."""

from typing import Any


def get_chroma_client() -> Any:
    """Return a persistent ChromaDB client using ``CHROMA_DB_PATH``.

    Returns:
        A Chroma client instance.

    Raises:
        NotImplementedError: Until ChromaDB is initialized.
    """
    raise NotImplementedError("ChromaDB client is not initialized yet.")


def get_or_create_collection(name: str = "omnirag") -> Any:
    """Get or create a named Chroma collection.

    Args:
        name: Collection name.

    Returns:
        A Chroma collection handle.

    Raises:
        NotImplementedError: Until collections are implemented.
    """
    raise NotImplementedError("Chroma collection access is not implemented yet.")
