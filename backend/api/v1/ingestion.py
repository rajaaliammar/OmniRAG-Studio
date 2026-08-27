"""Placeholder routes for document and URL ingestion."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/")
def ingest_source() -> dict[str, str]:
    """Accept a PDF, CSV, or web URL for indexing.

    Raises:
        HTTPException: Always, until ingestion is implemented.
    """
    raise HTTPException(
        status_code=501,
        detail="Document/URL ingestion is not implemented yet.",
    )
