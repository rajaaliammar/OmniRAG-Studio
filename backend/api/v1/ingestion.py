"""Routes for document and URL ingestion."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from langchain_core.documents import Document
from pydantic import BaseModel, Field, HttpUrl, field_validator

from backend.config import get_settings
from backend.ingestion.csv_loader import load_csv
from backend.ingestion.errors import IngestionError
from backend.ingestion.pdf_loader import load_pdf
from backend.ingestion.text_splitter import split_documents
from backend.ingestion.web_loader import load_url
from backend.vectorstore.chroma_db import add_documents_to_vectorstore
from backend.vectorstore.errors import VectorStoreError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_SNIPPET_LIMIT = 3
_SNIPPET_CHARS = 300
Loader = Callable[..., list[Document]]


class UrlIngestRequest(BaseModel):
    """JSON body for URL ingestion."""

    url: HttpUrl = Field(..., description="Public HTTP(S) page to ingest.")
    collection_name: str = Field(
        default="default_collection",
        description="ChromaDB collection to store chunks in.",
        min_length=1,
        max_length=63,
    )

    @field_validator("collection_name")
    @classmethod
    def _strip_collection_name(cls, value: str) -> str:
        """Reject blank collection names after trimming."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("collection_name must not be empty.")
        return cleaned


class DocumentPayload(BaseModel):
    """A pre-parsed document (or chunk) to persist."""

    page_content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoreRequest(BaseModel):
    """JSON body for embedding and storing prepared documents."""

    documents: list[DocumentPayload] = Field(..., min_length=1)
    collection_name: str = Field(
        default="default_collection",
        description="ChromaDB collection to store chunks in.",
        min_length=1,
        max_length=63,
    )

    @field_validator("collection_name")
    @classmethod
    def _strip_collection_name(cls, value: str) -> str:
        """Reject blank collection names after trimming."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("collection_name must not be empty.")
        return cleaned


class IngestResponse(BaseModel):
    """Parsed ingestion result for client verification."""

    source: str
    document_count: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    snippets: list[str]
    collection_name: str
    stored_count: int = Field(..., ge=0)


def _snippet(text: str) -> str:
    """Return a short preview of extracted text."""
    compact = " ".join(text.split())
    if len(compact) <= _SNIPPET_CHARS:
        return compact
    return compact[:_SNIPPET_CHARS].rstrip() + "..."


def _collection_name(value: str | None) -> str:
    """Return a non-empty collection name, defaulting from settings."""
    default = get_settings().default_collection_name
    cleaned = (value or "").strip()
    return cleaned or default


def _to_response(
    source: str,
    documents: list[Document],
    collection_name: str,
) -> IngestResponse:
    """Split loaded documents, persist embeddings, and build the API payload."""
    if not documents:
        raise IngestionError("No extractable text was found in the source.")
    chunks = split_documents(documents)
    name = _collection_name(collection_name)
    stored_count = add_documents_to_vectorstore(name, chunks)
    snippets = [_snippet(chunk.page_content) for chunk in chunks[:_SNIPPET_LIMIT]]
    return IngestResponse(
        source=source,
        document_count=len(documents),
        chunk_count=len(chunks),
        snippets=snippets,
        collection_name=name,
        stored_count=stored_count,
    )


def _http_error(exc: Exception) -> HTTPException:
    """Map domain ingestion errors onto HTTP status codes."""
    if isinstance(exc, HTTPException):
        return exc
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
    if isinstance(exc, VectorStoreError):
        message = str(exc).lower()
        if "not found" in message:
            return HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )
        if "rate-limited" in message or "rate limit" in message:
            return HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
            )
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
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


async def _ingest_upload(
    file: UploadFile,
    collection_name: str,
    allowed_suffixes: tuple[str, ...],
    loader: Loader,
) -> IngestResponse:
    """Shared upload path: validate, load, chunk, and persist."""
    payload, filename = await _read_upload(file, allowed_suffixes)
    try:
        documents = await asyncio.to_thread(
            loader, payload, source_name=filename
        )
        return await asyncio.to_thread(
            _to_response, filename, documents, collection_name
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(..., description="PDF or CSV file to ingest"),
    collection_name: str = Form(
        "default_collection",
        description="ChromaDB collection to store chunks in.",
    ),
) -> IngestResponse:
    """Ingest a PDF or CSV, dispatching by file extension."""
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix == ".pdf":
        return await _ingest_upload(file, collection_name, (".pdf",), load_pdf)
    if suffix == ".csv":
        return await _ingest_upload(file, collection_name, (".csv",), load_csv)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Expected a .pdf or .csv file; got '{file.filename or 'upload'}'."
        ),
    )


@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(..., description="PDF document to ingest"),
    collection_name: str = Form(
        "default_collection",
        description="ChromaDB collection to store chunks in.",
    ),
) -> IngestResponse:
    """Load a PDF, chunk it, embed it, and persist it to ChromaDB."""
    return await _ingest_upload(file, collection_name, (".pdf",), load_pdf)


@router.post("/csv", response_model=IngestResponse)
async def ingest_csv(
    file: UploadFile = File(..., description="CSV file to ingest"),
    collection_name: str = Form(
        "default_collection",
        description="ChromaDB collection to store chunks in.",
    ),
) -> IngestResponse:
    """Load a CSV, chunk it, embed it, and persist it to ChromaDB."""
    return await _ingest_upload(file, collection_name, (".csv",), load_csv)


@router.post("/url", response_model=IngestResponse)
def ingest_url(body: UrlIngestRequest) -> IngestResponse:
    """Fetch a web page, chunk it, embed it, and persist it to ChromaDB."""
    url = str(body.url)
    try:
        documents = load_url(url)
        if not documents:
            raise IngestionError(f"No extractable text found at '{url}'.")
        source = str(documents[0].metadata.get("source") or url)
        return _to_response(source, documents, body.collection_name)
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/store", response_model=IngestResponse)
def ingest_store(body: StoreRequest) -> IngestResponse:
    """Embed prepared documents and save them into a ChromaDB collection."""
    try:
        documents = [
            Document(page_content=item.page_content, metadata=item.metadata)
            for item in body.documents
        ]
        return _to_response("store", documents, body.collection_name)
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc
