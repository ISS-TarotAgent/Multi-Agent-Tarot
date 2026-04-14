from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Protocol

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


class _NoOpObservationHandle:
    def success(
        self,
        *,
        output: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        return None

    def failure(
        self,
        *,
        error_code: str | None,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        return None


class _LangfuseObservationHandle:
    def __init__(self, observation) -> None:  # noqa: ANN001
        self._observation = observation

    def success(
        self,
        *,
        output: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._update(output=output, metadata=metadata)

    def failure(
        self,
        *,
        error_code: str | None,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        output = {"message": message}
        if error_code is not None:
            output["error_code"] = error_code
        self._update(output=output, metadata=metadata, level="ERROR", status_message=message)

    def _update(
        self,
        *,
        output: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        kwargs: dict[str, object] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        if level is not None:
            kwargs["level"] = level
        if status_message is not None:
            kwargs["status_message"] = status_message
        if kwargs:
            self._observation.update(**kwargs)


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
    ) -> Iterator[_NoOpObservationHandle]:
        yield _NoOpObservationHandle()

    @contextmanager
    def observe_step(
        self,
        *,
        step_name: str,
        as_type: str,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Iterator[_NoOpObservationHandle]:
        yield _NoOpObservationHandle()

    @staticmethod
    def get_current_trace_id() -> str | None:
        return None


class LangfuseWorkflowObserver:
    def __init__(self, client) -> None:  # noqa: ANN001
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
    ) -> Iterator[_LangfuseObservationHandle]:
        merged_metadata = _merge_metadata(
            metadata,
            session_id=session_id,
            reading_id=reading_id,
        )
        with self._client.start_as_current_observation(
            name=name,
            as_type="chain",
            input=input_payload,
            metadata=merged_metadata,
        ) as observation:
            yield _LangfuseObservationHandle(observation)

    @contextmanager
    def observe_step(
        self,
        *,
        step_name: str,
        as_type: str,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Iterator[_LangfuseObservationHandle]:
        with self._client.start_as_current_observation(
            name=step_name,
            as_type=as_type,
            input=input_payload,
            metadata=metadata,
        ) as observation:
            yield _LangfuseObservationHandle(observation)

    def get_current_trace_id(self) -> str | None:
        return self._client.get_current_trace_id()


def build_workflow_observer(settings: AppSettings) -> NoOpWorkflowObserver | LangfuseWorkflowObserver:
    if not settings.langfuse_enabled:
        return NoOpWorkflowObserver()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning(
            "langfuse_disabled_missing_credentials",
            extra={
                "environment": settings.app_env,
            },
        )
        return NoOpWorkflowObserver()

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.warning(
            "langfuse_disabled_missing_sdk",
            extra={
                "environment": settings.app_env,
            },
        )
        return NoOpWorkflowObserver()

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_base_url,
    )
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
