"""Clarifier node implementation used by the LangGraph workflow."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol

from agent.schemas.clarifier import ClarifierInput, ClarifierOutput
from backend.app.domain.enums import TraceEventStatus, WorkflowStatus
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload


class ClarifierAgent(Protocol):
    def run(self, payload: ClarifierInput) -> ClarifierOutput: ...


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


class WorkflowObserver(Protocol):
    def observe_step(
        self,
        *,
        step_name: str,
        as_type: str,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ): ...


class TraceEventFactory(Protocol):
    def __call__(
        self,
        *,
        step_name: str,
        event_status: TraceEventStatus,
        attempt_no: int,
        payload: dict[str, Any],
        started: float | None,
        error_code: str | None = None,
    ) -> TraceEventPayload: ...


class TraceLogger(Protocol):
    def __call__(
        self,
        *,
        state: TarotWorkflowState,
        reading_id: str | None,
        only_latest: bool = False,
    ) -> None: ...


def execute_clarifier_step(
    *,
    state: TarotWorkflowState,
    clarifier_agent: ClarifierAgent,
    observer: WorkflowObserver,
    trace_event_factory: TraceEventFactory,
    trace_logger: TraceLogger,
    trace_reading_id: str | None = None,
) -> TarotWorkflowState:
    question_text = state.effective_question or state.raw_question
    payload = ClarifierInput(raw_question=question_text, locale=state.locale)
    reading_id = trace_reading_id or state.reading_id

    with observer.observe_step(
        step_name="clarifier",
        as_type="chain",
        input_payload={"raw_question": question_text},
        metadata={"session_id": state.session_id, "reading_id": reading_id},
    ) as observation:
        started = perf_counter()
        try:
            clarification = clarifier_agent.run(payload)
            state.trace_events.append(
                trace_event_factory(
                    step_name="clarifier",
                    event_status=TraceEventStatus.SUCCEEDED,
                    attempt_no=1,
                    started=started,
                    payload={
                        "clarification_required": clarification.clarification_required,
                        "normalized_question": clarification.normalized_question,
                    },
                )
            )
            state.clarification_output = clarification
            state.normalized_question = clarification.normalized_question
            state.status = (
                WorkflowStatus.CLARIFYING
                if clarification.clarification_required
                else WorkflowStatus.READY_FOR_DRAW
            )
            observation.success(
                output={
                    "status": state.status.value,
                    "clarification_required": clarification.clarification_required,
                }
            )
        except Exception as exc:  # pragma: no cover - exercised by backend tests
            fallback = ClarifierOutput(
                normalized_question=question_text,
                clarification_required=False,
                clarifier_question=None,
            )
            metadata_payload = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "fallback_normalized_question": question_text,
            }
            state.trace_events.append(
                trace_event_factory(
                    step_name="clarifier",
                    event_status=TraceEventStatus.FALLBACK,
                    attempt_no=1,
                    started=started,
                    error_code="CLARIFIER_FALLBACK_TO_RAW",
                    payload=metadata_payload,
                )
            )
            state.clarification_output = fallback
            state.normalized_question = question_text
            state.status = WorkflowStatus.READY_FOR_DRAW
            observation.failure(
                error_code="CLARIFIER_FALLBACK_TO_RAW",
                message="Clarifier failed; used the raw question as fallback.",
                metadata=metadata_payload,
            )

    trace_logger(state=state, reading_id=trace_reading_id, only_latest=False)
    return state
