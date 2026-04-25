"""Thread-safe context variable holding the active Langfuse observation.

WorkflowObserver sets/resets this around each step; ModelGateway reads it to
attach LLM generations as children without needing an explicit parameter.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_current: ContextVar[Any] = ContextVar("langfuse_observation", default=None)


def set_observation(obs: Any) -> Any:
    """Set current observation; returns the ContextVar token for reset."""
    return _current.set(obs)


def reset_observation(token: Any) -> None:
    _current.reset(token)


def get_observation() -> Any | None:
    return _current.get()
