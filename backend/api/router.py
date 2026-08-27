"""Root API router that mounts versioned sub-routers."""

from fastapi import APIRouter

from backend.api.v1 import analytics, chat, ingestion

api_router = APIRouter(prefix="/api")
api_router.include_router(ingestion.router, prefix="/v1")
api_router.include_router(chat.router, prefix="/v1")
api_router.include_router(analytics.router, prefix="/v1")
