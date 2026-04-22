from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator, Protocol

from app.infrastructure.config.settings import AppSettings

logger = logging.getLogger("app.observability")


class ObservationHandle(Protocol):
    def success(
        self,
        *,
        output: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None: ...

    def failure(
        self,
        *,
        error_code: str | None,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# No-op implementation
# ---------------------------------------------------------------------------

class _NoOpHandle:
    def success(self, *, output=None, metadata=None) -> None:
        pass

    def failure(self, *, error_code=None, message="", metadata=None) -> None:
        pass


class NoOpWorkflowObserver:
    @contextmanager
    def observe_operation(
        self,
        *,
        name: str,
        session_id: str,
        reading_id: str | None,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Iterator[_NoOpHandle]:
        yield _NoOpHandle()

    @contextmanager
    def observe_step(
        self,
        *,
        step_name: str,
        as_type: str,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Iterator[_NoOpHandle]:
        yield _NoOpHandle()

    @staticmethod
    def get_current_trace_id() -> str | None:
        return None


# ---------------------------------------------------------------------------
# Langfuse v2 low-level implementation
# ---------------------------------------------------------------------------

class _LangfuseHandle:
    """Collects success/failure output; the caller ends the observation."""

    def __init__(self) -> None:
        self.end_kwargs: dict[str, Any] = {}

    def success(
        self,
        *,
        output: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if output is not None:
            self.end_kwargs["output"] = output
        if metadata is not None:
            self.end_kwargs["metadata"] = metadata

    def failure(
        self,
        *,
        error_code: str | None = None,
        message: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None:
        out: dict[str, object] = {"message": message}
        if error_code is not None:
            out["error_code"] = error_code
        self.end_kwargs["output"] = out
        self.end_kwargs["level"] = "ERROR"
        self.end_kwargs["status_message"] = message
        if metadata is not None:
            self.end_kwargs["metadata"] = metadata


class LangfuseWorkflowObserver:
    def __init__(self, client: Any) -> None:
        self._client = client

    @contextmanager
    def observe_operation(
        self,
        *,
        name: str,
        session_id: str,
        reading_id: str | None,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Iterator[_LangfuseHandle]:
        from agent.core.trace_context import reset_observation, set_observation  # noqa: PLC0415

        trace = self._client.trace(
            id=reading_id,
            name=name,
            session_id=session_id,
            input=input_payload,
            metadata=_merge_metadata(metadata, session_id=session_id, reading_id=reading_id),
        )
        token = set_observation(trace)
        handle = _LangfuseHandle()
        try:
            yield handle
        finally:
            trace.update(**handle.end_kwargs)
            reset_observation(token)

    @contextmanager
    def observe_step(
        self,
        *,
        step_name: str,
        as_type: str,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Iterator[_LangfuseHandle]:
        from agent.core.trace_context import get_observation, reset_observation, set_observation  # noqa: PLC0415

        parent = get_observation()
        if parent is None:
            yield _NoOpHandle()  # type: ignore[misc]
            return

        span = parent.span(name=step_name, input=input_payload, metadata=metadata)
        token = set_observation(span)
        handle = _LangfuseHandle()
        try:
            yield handle
        finally:
            span.end(**handle.end_kwargs)
            reset_observation(token)

    def get_current_trace_id(self) -> str | None:
        from agent.core.trace_context import get_observation  # noqa: PLC0415
        obs = get_observation()
        return getattr(obs, "id", None) if obs is not None else None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_workflow_observer(settings: AppSettings) -> NoOpWorkflowObserver | LangfuseWorkflowObserver:
    if not settings.langfuse_enabled:
        return NoOpWorkflowObserver()

    try:
        from agent.core.langfuse_client import get_langfuse  # noqa: PLC0415
    except ImportError:
        logger.warning("langfuse_disabled_missing_sdk", extra={"environment": settings.app_env})
        return NoOpWorkflowObserver()

    client = get_langfuse()
    if client is None:
        logger.warning("langfuse_disabled_missing_credentials", extra={"environment": settings.app_env})
        return NoOpWorkflowObserver()

    return LangfuseWorkflowObserver(client=client)


def _merge_metadata(
    metadata: dict[str, object] | None,
    *,
    session_id: str,
    reading_id: str | None,
) -> dict[str, object]:
    merged = dict(metadata or {})
    merged["session_id"] = session_id
    if reading_id is not None:
        merged["reading_id"] = reading_id
    return merged
