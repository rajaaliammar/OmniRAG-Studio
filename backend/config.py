"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for OmniRAG Studio.

    Values are read from the process environment and an optional `.env` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    chroma_db_path: str = "./chromadb_data"
    database_url: str = "sqlite:///./analytics.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    app_name: str = "OmniRAG Studio"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
