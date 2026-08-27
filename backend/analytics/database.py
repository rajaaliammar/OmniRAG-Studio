"""SQLAlchemy engine and session factory."""

from typing import Any


def get_engine() -> Any:
    """Create the SQLAlchemy engine from ``DATABASE_URL``.

    Returns:
        A SQLAlchemy Engine.

    Raises:
        NotImplementedError: Until the database layer is implemented.
    """
    raise NotImplementedError("Database engine is not initialized yet.")


def get_session() -> Any:
    """Yield a database session.

    Returns:
        A SQLAlchemy Session.

    Raises:
        NotImplementedError: Until sessions are implemented.
    """
    raise NotImplementedError("Database session factory is not implemented yet.")
