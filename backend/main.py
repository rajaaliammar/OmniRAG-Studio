"""OmniRAG Studio FastAPI application entrypoint."""

import uvicorn
from fastapi import FastAPI

from backend.api.router import api_router
from backend.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Multi-source RAG chatbot with real-time analytics.",
    version="0.1.0",
)

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
