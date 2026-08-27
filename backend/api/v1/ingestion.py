"""Routes for document and URL ingestion."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from langchain_core.documents import Document
from pydantic import BaseModel, Field, HttpUrl

from backend.ingestion.csv_loader import load_csv
from backend.ingestion.errors import IngestionError
from backend.ingestion.pdf_loader import load_pdf
from backend.ingestion.text_splitter import split_documents
from backend.ingestion.web_loader import load_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_SNIPPET_LIMIT = 3
_SNIPPET_CHARS = 300


class UrlIngestRequest(BaseModel):
    """JSON body for URL ingestion."""

    url: HttpUrl = Field(..., description="Public HTTP(S) page to ingest.")


class IngestResponse(BaseModel):
    """Parsed ingestion result for client verification."""

    source: str
    document_count: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    snippets: list[str]


def _snippet(text: str) -> str:
    """Return a short preview of extracted text."""
    compact = " ".join(text.split())
    if len(compact) <= _SNIPPET_CHARS:
        return compact
    return compact[:_SNIPPET_CHARS].rstrip() + "..."


def _to_response(source: str, documents: list[Document]) -> IngestResponse:
    """Split loaded documents and build the API payload."""
    chunks = split_documents(documents)
    snippets = [_snippet(chunk.page_content) for chunk in chunks[:_SNIPPET_LIMIT]]
    return IngestResponse(
        source=source,
        document_count=len(documents),
        chunk_count=len(chunks),
        snippets=snippets,
    )


def _http_error(exc: Exception) -> HTTPException:
    """Map domain ingestion errors onto HTTP status codes."""
    if isinstance(exc, FileNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, IngestionError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    logger.exception("Unexpected ingestion failure")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Ingestion failed due to an unexpected server error.",
    )


async def _read_upload(
    file: UploadFile,
    allowed_suffixes: tuple[str, ...],
) -> tuple[bytes, str]:
    """Read and validate an uploaded file."""
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        allowed = ", ".join(allowed_suffixes)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Expected a file with extension {allowed}; got '{filename}'."
            ),
        )
    payload = await file.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(payload) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 25 MB upload limit.",
        )
    return payload, filename


@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(..., description="PDF document to ingest"),
) -> IngestResponse:
    """Load a PDF, split it into chunks, and return counts plus snippets."""
    payload, filename = await _read_upload(file, (".pdf",))
    try:
        documents = load_pdf(payload, source_name=filename)
        return _to_response(filename, documents)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/csv", response_model=IngestResponse)
async def ingest_csv(
    file: UploadFile = File(..., description="CSV file to ingest"),
) -> IngestResponse:
    """Load a CSV, split row documents, and return counts plus snippets."""
    payload, filename = await _read_upload(file, (".csv",))
    try:
        documents = load_csv(payload, source_name=filename)
        return _to_response(filename, documents)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/url", response_model=IngestResponse)
def ingest_url(body: UrlIngestRequest) -> IngestResponse:
    """Fetch a web page, split its content, and return counts plus snippets."""
    url = str(body.url)
    try:
        documents = load_url(url)
        source = str(documents[0].metadata.get("source") or url)
        return _to_response(source, documents)
    except Exception as exc:
        raise _http_error(exc) from exc
