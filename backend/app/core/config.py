"""Application configuration (Python 3.12 runtime)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global configuration sourced from environment variables.

    Target runtime is **Python 3.12**, so downstream modules should rely on
    typing/asyncio features available in 3.12.

    TODO:
        - add OpenAI/model gateway keys
        - add database DSN + pool sizing
        - add observability toggles (Langfuse, JSON log level)
    """

    environment: str = "dev"


@lru_cache
def get_settings() -> Settings:
    """Provide a cached Settings instance for dependency injection."""

    return Settings()  # type: ignore[arg-type]
