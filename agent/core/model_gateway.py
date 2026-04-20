"""OpenAI model gateway for the Multi-Agent Tarot system.

All LLM calls within agent nodes should go through this abstraction instead of
calling the OpenAI SDK directly.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModelResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelGateway(ABC):
    """Uniform interface for LLM providers."""

    @abstractmethod
    def run(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse: ...


class OpenAIModelGateway(ModelGateway):
    """Concrete gateway backed by the OpenAI chat completions API."""

    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 2048
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 1,
    ) -> None:
        from openai import OpenAI

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model or os.environ.get("OPENAI_MODEL", self.DEFAULT_MODEL)
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = OpenAI(
            api_key=resolved_key,
            timeout=float(timeout),
            max_retries=max_retries,
        )

    def run(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature if temperature is not None else self._temperature,
            max_tokens=max_tokens if max_tokens is not None else self._max_tokens,
            **kwargs,
        )

        choice = response.choices[0]
        usage = response.usage
        return ModelResponse(
            content=choice.message.content or "",
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )


def build_gateway_from_settings() -> OpenAIModelGateway:
    """Construct an OpenAIModelGateway using AppSettings when available."""
    try:
        from backend.app.infrastructure.config.settings import get_settings
        s = get_settings()
        return OpenAIModelGateway(
            api_key=s.openai_api_key,
            model=s.openai_model,
            timeout=s.model_timeout_seconds,
            max_retries=s.model_max_retries,
        )
    except Exception:
        return OpenAIModelGateway()
