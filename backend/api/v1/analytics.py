"""Placeholder routes for admin analytics and cost metrics."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/metrics")
def get_metrics() -> dict[str, str]:
    """Return query volume, latency, and estimated LLM cost.

    Raises:
        HTTPException: Always, until analytics queries are implemented.
    """
    raise HTTPException(
        status_code=501,
        detail="Analytics metrics are not implemented yet.",
    )
