"""Query and cost logging helpers."""

from typing import Any


def log_query(question: str, metadata: dict[str, Any] | None = None) -> None:
    """Persist a chat query event to SQLite.

    Args:
        question: User question text.
        metadata: Optional latency, token, and model fields.

    Raises:
        NotImplementedError: Until logging is implemented.
    """
    raise NotImplementedError("Query logging is not implemented yet.")


def log_cost(query_id: str, usd_amount: float) -> None:
    """Persist estimated LLM cost for a query.

    Args:
        query_id: Identifier of the related query log row.
        usd_amount: Estimated cost in USD.

    Raises:
        NotImplementedError: Until cost logging is implemented.
    """
    raise NotImplementedError("Cost logging is not implemented yet.")
