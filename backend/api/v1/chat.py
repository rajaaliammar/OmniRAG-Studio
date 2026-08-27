"""Placeholder routes for RAG chat and streaming responses."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/")
def chat() -> dict[str, str]:
    """Run a RAG query and return an answer with citations.

    Raises:
        HTTPException: Always, until the RAG chain is implemented.
    """
    raise HTTPException(
        status_code=501,
        detail="RAG chat is not implemented yet.",
    )


@router.post("/stream")
def chat_stream() -> dict[str, str]:
    """Stream a RAG answer token-by-token.

    Raises:
        HTTPException: Always, until streaming is implemented.
    """
    raise HTTPException(
        status_code=501,
        detail="Streaming RAG chat is not implemented yet.",
    )
