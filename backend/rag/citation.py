"""Source citation formatting for RAG answers."""

from typing import Any


def format_citations(documents: list[Any]) -> list[dict[str, str]]:
    """Turn retrieved documents into citation payloads.

    Args:
        documents: Retriever hits (LangChain Documents or equivalents).

    Returns:
        A list of ``source``, ``snippet``, and optional ``page`` mappings.

    Raises:
        NotImplementedError: Until citation formatting is implemented.
    """
    raise NotImplementedError("Citation formatting is not implemented yet.")
