"""SQLAlchemy ORM models for query and cost logs."""

# Placeholder: QueryLog and CostLog models will live here.


class QueryLog:
    """Record of a single RAG query (timestamp, latency, token usage)."""

    __tablename__ = "query_logs"


class CostLog:
    """Estimated LLM/embedding cost associated with a query."""

    __tablename__ = "cost_logs"
