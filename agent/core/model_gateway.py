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
        generation_name: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        effective_temp = temperature if temperature is not None else self._temperature
        effective_max = max_tokens if max_tokens is not None else self._max_tokens

        generation = self._start_generation(
            name=generation_name or self._model,
            messages=messages,
            temperature=effective_temp,
            max_tokens=effective_max,
        )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=effective_temp,
            max_tokens=effective_max,
            **kwargs,
        )

        choice = response.choices[0]
        usage = response.usage
        content = choice.message.content or ""

        self._end_generation(generation, output=content, usage=usage)

        return ModelResponse(
            content=content,
            model=response.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    def _start_generation(
        self,
        *,
        name: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Any:
        try:
            from agent.core.trace_context import get_observation  # noqa: PLC0415
            obs = get_observation()
            if obs is None:
                return None
            return obs.generation(
                name=name,
                model=self._model,
                input=messages,
                model_parameters={"temperature": temperature, "max_tokens": max_tokens},
            )
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _end_generation(generation: Any, *, output: str, usage: Any) -> None:
        if generation is None:
            return
        try:
            generation.end(
                output=output,
                usage={
                    "input": usage.prompt_tokens if usage else 0,
                    "output": usage.completion_tokens if usage else 0,
                },
            )
        except Exception:  # noqa: BLE001
            pass


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
