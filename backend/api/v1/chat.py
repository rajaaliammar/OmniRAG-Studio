"""Routes for RAG chat with citations and session memory."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.config import get_settings
from backend.rag.chain import answer_query
from backend.rag.errors import RagError
from backend.rag.memory import get_memory
from backend.vectorstore.chroma_db import collection_exists
from backend.vectorstore.errors import VectorStoreError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatQueryRequest(BaseModel):
    """JSON body for a grounded RAG question."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="User question.",
    )
    collection_name: str = Field(
        default="default_collection",
        min_length=1,
        max_length=63,
        description="Chroma collection to retrieve from.",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        description="Optional conversation id for multi-turn memory.",
    )

    @field_validator("query")
    @classmethod
    def _strip_query(cls, value: str) -> str:
        """Reject whitespace-only questions."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be empty.")
        return cleaned

    @field_validator("collection_name")
    @classmethod
    def _strip_collection_name(cls, value: str) -> str:
        """Reject blank collection names after trimming."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("collection_name must not be empty.")
        return cleaned

    @field_validator("session_id")
    @classmethod
    def _strip_session_id(cls, value: str | None) -> str | None:
        """Normalize optional session ids."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class Citation(BaseModel):
    """One retrieved source locator."""

    model_config = ConfigDict(populate_by_name=True)

    source: str
    page_row: str = Field(
        default="",
        alias="page/row",
        serialization_alias="page/row",
        description="Page number, CSV row index, or URL.",
    )


class ChatQueryResponse(BaseModel):
    """Grounded answer with citations and session id."""

    model_config = ConfigDict(populate_by_name=True)

    answer: str
    citations: list[Citation]
    session_id: str


class ClearMemoryRequest(BaseModel):
    """JSON body to drop a conversation session."""

    session_id: str = Field(..., min_length=1, max_length=128)

    @field_validator("session_id")
    @classmethod
    def _strip_session_id(cls, value: str) -> str:
        """Reject whitespace-only session ids."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("session_id must not be empty.")
        return cleaned


class ClearMemoryResponse(BaseModel):
    """Result of clearing conversational memory."""

    session_id: str
    cleared: bool


def _http_error(exc: Exception) -> HTTPException:
    """Map domain RAG errors onto HTTP status codes."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    if isinstance(exc, RagError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
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
    logger.exception("Unexpected chat failure")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Chat failed due to an unexpected server error.",
    )


@router.post("/query", response_model=ChatQueryResponse)
def chat_query(body: ChatQueryRequest) -> ChatQueryResponse:
    """Retrieve context, generate a grounded answer, and return citations."""
    settings = get_settings()
    collection = body.collection_name.strip() or settings.default_collection_name
    if not collection_exists(collection):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Collection '{collection}' was not found. "
                "Ingest documents first."
            ),
        )
    try:
        result = answer_query(
            body.query,
            collection,
            session_id=body.session_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(exc) from exc
    citations = [
        Citation.model_validate(
            {
                "source": item.get("source", "unknown"),
                "page/row": item.get("page/row", ""),
            }
        )
        for item in result.citations
    ]
    return ChatQueryResponse(
        answer=result.answer,
        citations=citations,
        session_id=result.session_id,
    )


@router.post("/clear", response_model=ClearMemoryResponse)
def chat_clear(body: ClearMemoryRequest) -> ClearMemoryResponse:
    """Clear conversational memory for a session."""
    session_id = body.session_id.strip()
    cleared = get_memory().clear(session_id)
    return ClearMemoryResponse(session_id=session_id, cleared=cleared)


@router.post("/stream")
def chat_stream() -> dict[str, str]:
    """Stream a RAG answer token-by-token.

    Raises:
        HTTPException: Always, until streaming is implemented.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Streaming RAG chat is not implemented yet.",
    )
