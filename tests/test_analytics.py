"""Tests for analytics logging."""

import pytest


def test_query_logger_placeholder() -> None:
    """Query logger should raise until implemented."""
    from backend.analytics.logger import log_query

    with pytest.raises(NotImplementedError):
        log_query("What is OmniRAG Studio?")


def test_cost_logger_placeholder() -> None:
    """Cost logger should raise until implemented."""
    from backend.analytics.logger import log_cost

    with pytest.raises(NotImplementedError):
        log_cost("query-1", 0.01)
