"""OmniRAG Studio FastAPI application entrypoint."""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.router import api_router
from backend.config import ENV_FILE, get_openai_api_key, get_settings, mask_secret

logger = logging.getLogger(__name__)

settings = get_settings()
_provider = (settings.embedding_provider or "huggingface").strip().lower()
print(f"[OmniRAG Studio] Embedding provider: {_provider or 'huggingface'}")
if _provider == "openai":
    _openai_key = get_openai_api_key()
    if _openai_key:
        print(
            f"[OmniRAG Studio] OPENAI_API_KEY detected: {mask_secret(_openai_key)} "
            f"(source file: {ENV_FILE})"
        )
    else:
        print(
            "[OmniRAG Studio] OPENAI_API_KEY was NOT detected. "
            f"Set it in {ENV_FILE} when EMBEDDING_PROVIDER=openai."
        )
else:
    print(
        "[OmniRAG Studio] Using local HuggingFace embeddings "
        f"({settings.embedding_model}). OPENAI_API_KEY is not required."
    )

app = FastAPI(
    title=settings.app_name,
    description=(
        "Multi-source RAG chatbot. Ingest PDFs, CSVs, and web pages into "
        "ChromaDB, then ask grounded questions at /api/v1/chat/query."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/v1/ingest, /api/v1/chat, /api/v1/analytics
app.include_router(api_router)


class HealthResponse(BaseModel):
    """Liveness payload for load balancers and local checks."""

    status: str = Field(..., min_length=1)
    app: str = Field(..., min_length=1)


def _validation_detail(exc: RequestValidationError) -> str | list[str]:
    """Flatten Pydantic errors into a readable client-facing message."""
    messages: list[str] = []
    for error in exc.errors():
        loc_parts = [
            str(part)
            for part in error.get("loc", ())
            if part not in {"body", "query", "path", "form"}
        ]
        location = ".".join(loc_parts)
        message = str(error.get("msg", "Invalid value"))
        messages.append(f"{location}: {message}" if location else message)
    if len(messages) == 1:
        return messages[0]
    return messages


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return HTTP 422 with a concise validation message."""
    del request
    return JSONResponse(
        status_code=422,
        content={"detail": _validation_detail(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Map unexpected errors to HTTP 500 without leaking internals."""
    del request
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": _validation_detail(exc)},
        )
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    logger.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    """Return application health status."""
    return HealthResponse(status="ok", app="OmniRAG Studio")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
