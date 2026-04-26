from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class ImageGenerationSettings(BaseSettings):
    """Standalone script settings sourced from env vars and backend/.env."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://ai.centos.hk", alias="OPENAI_BASE_URL")
    openai_image_model: str = Field(default="gpt-image-2", alias="OPENAI_IMAGE_MODEL")
    openai_image_size: str | None = Field(default=None, alias="OPENAI_IMAGE_SIZE")
    openai_image_timeout_seconds: int = Field(default=300, alias="OPENAI_IMAGE_TIMEOUT_SECONDS")
    openai_image_max_retries: int = Field(default=3, alias="OPENAI_IMAGE_MAX_RETRIES")

    @field_validator("openai_image_size", mode="before")
    @classmethod
    def normalize_optional_size(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def images_generations_url(self) -> str:
        base = self.openai_base_url.rstrip("/")
        if base.endswith("/images/generations"):
            return base
        if base.endswith("/v1"):
            return f"{base}/images/generations"
        return f"{base}/v1/images/generations"

    @property
    def default_output_root(self) -> Path:
        return REPO_ROOT / "generated" / "tarot-cards"

    def require_api_key(self) -> str:
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for live image generation requests.")
        return self.openai_api_key


@lru_cache
def get_image_generation_settings() -> ImageGenerationSettings:
    return ImageGenerationSettings()
