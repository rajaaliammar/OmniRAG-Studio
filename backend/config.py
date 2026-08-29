"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/config.py -> project root (parent of ``backend/``)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env() -> Path:
    """Load ``.env`` from the project root, independent of the process CWD.

    Returns:
        Absolute path to the ``.env`` file (may not exist yet).
    """
    load_dotenv(dotenv_path=ENV_FILE, override=False, encoding="utf-8")
    return ENV_FILE


load_project_env()


class Settings(BaseSettings):
    """Runtime settings for OmniRAG Studio.

    Values come from the process environment and the project-root ``.env``
    file. Empty environment variables are ignored so a blank shell binding
    cannot hide a value defined in ``.env``.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        case_sensitive=False,
    )

    openai_api_key: str = ""
    chroma_db_path: str = "./chromadb_data"
    database_url: str = "sqlite:///./analytics.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    app_name: str = "OmniRAG Studio"
    embedding_provider: str = "huggingface"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_fallback_provider: str = ""
    embedding_fallback_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 64
    default_collection_name: str = "default_collection"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    rag_top_k: int = 4
    rag_score_threshold: float = 0.0
    chat_memory_max_turns: int = 12

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def _strip_openai_api_key(cls, value: object) -> object:
        """Trim whitespace and wrapping quotes from the API key."""
        if not isinstance(value, str):
            return value
        return value.strip().strip('"').strip("'")


def mask_secret(value: str, visible: int = 6) -> str:
    """Mask a secret, leaving only the first ``visible`` characters.

    Args:
        value: Raw secret string.
        visible: Number of leading characters to keep.

    Returns:
        A display-safe string such as ``sk-pro****************``.
    """
    cleaned = (value or "").strip()
    if not cleaned:
        return "(not set)"
    prefix_len = min(visible, len(cleaned))
    return cleaned[:prefix_len] + ("*" * max(len(cleaned) - prefix_len, 0))


def get_openai_api_key() -> str:
    """Return ``OPENAI_API_KEY`` from settings, falling back to ``os.getenv``.

    Returns:
        The stripped API key, or an empty string if it is missing.
    """
    load_project_env()
    from_settings = (get_settings().openai_api_key or "").strip()
    from_environ = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    return from_settings or from_environ


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance after loading the project ``.env``."""
    load_project_env()
    return Settings()
