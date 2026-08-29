"""OmniRAG Studio FastAPI application entrypoint."""

import uvicorn
from fastapi import FastAPI

from backend.api.router import api_router
from backend.config import ENV_FILE, get_openai_api_key, get_settings, mask_secret

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
        "Multi-source RAG chatbot with real-time analytics. "
        "Chat lives at /api/v1/chat/query."
    ),
    version="0.1.0",
)

# /api/v1/ingest, /api/v1/chat, /api/v1/analytics
app.include_router(api_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """Return application health status."""
    return {"status": "ok", "app": "OmniRAG Studio"}


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
