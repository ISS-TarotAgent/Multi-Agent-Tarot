"""Abstractions for LLM access.

The ModelGateway should hide provider-specific details (OpenAI, Azure, etc.) and
expose a consistent `run(prompt, **kwargs)` interface. Concrete transport code is
left to future implementers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass
class ModelInvocationContext:
    """Carries observability metadata for a single LLM call.

    TODO:
        - add trace/span ids for Langfuse
        - add prompt version references
        - add user/session attribution for auditing
    """

    metadata: Mapping[str, Any] | None = None


class ModelGateway(ABC):
    """Base gateway definition."""

    @abstractmethod
    def run(self, prompt: str, *, context: Optional[ModelInvocationContext] = None, **kwargs: Any) -> str:
        """Execute a prompt against the configured provider.

        TODO:
            - add streaming hook support
            - add retry/budget policies
            - add structured logging integration
        """

        raise NotImplementedError


class OpenAIModelGateway(ModelGateway):
    """Placeholder for the default provider implementation.

    TODO:
        - wire to OpenAI client
        - expose model/temperature configuration
        - emit structured logs
    """

    def run(self, prompt: str, *, context: Optional[ModelInvocationContext] = None, **kwargs: Any) -> str:
        # TODO: implement provider call
        raise NotImplementedError("OpenAIModelGateway.run is pending implementation")
