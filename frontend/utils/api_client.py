"""HTTP client for the OmniRAG Studio FastAPI backend."""

from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def healthcheck(base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    """Call ``GET /health`` on the backend.

    Args:
        base_url: FastAPI origin, including scheme and port.

    Returns:
        Parsed JSON health payload.

    Raises:
        NotImplementedError: Until the HTTP client is implemented.
    """
    raise NotImplementedError("API client is not implemented yet.")
