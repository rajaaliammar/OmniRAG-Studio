"""Routes for RAG chat with citations and session memory."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.config import get_settings
from backend.rag.chain import answer_query
from backend.rag.errors import RagError
from backend.rag.memory import get_memory
from backend.vectorstore.errors import VectorStoreError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatQueryRequest(BaseModel):
    """JSON body for a grounded RAG question."""

    query: str = Field(..., min_length=1, description="User question.")
    collection_name: str = Field(
        default="default_collection",
        min_length=1,
        description="Chroma collection to retrieve from.",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional conversation id for multi-turn memory.",
    )


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

    session_id: str = Field(..., min_length=1)


class ClearMemoryResponse(BaseModel):
    """Result of clearing conversational memory."""

    session_id: str
    cleared: bool


def _http_error(exc: Exception) -> HTTPException:
    """Map domain RAG errors onto HTTP status codes."""
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
    collection = (body.collection_name or "").strip() or settings.default_collection_name
    try:
        result = answer_query(
            body.query,
            collection,
            session_id=body.session_id,
        )
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
