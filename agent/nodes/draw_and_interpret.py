"""Draw and interpret node implementation used by the LangGraph workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol

from agent.schemas.draw import DrawInput, DrawOutput
from agent.schemas.safety import SafetyReviewOutput
from backend.app.domain.enums import TraceEventStatus, WorkflowStatus
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload


class DrawAgent(Protocol):
    def run(self, payload: DrawInput) -> DrawOutput: ...


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


class ProtectiveFallbackFactory(Protocol):
    def __call__(self, *, review_notes: str) -> SafetyReviewOutput: ...


def execute_draw_step(
    *,
    state: TarotWorkflowState,
    draw_agent: DrawAgent,
    observer: WorkflowObserver,
    trace_event_factory: TraceEventFactory,
    trace_logger: TraceLogger,
    protective_fallback_factory: ProtectiveFallbackFactory,
) -> TarotWorkflowState:
    payload = DrawInput(
        question=state.normalized_question or state.raw_question,
        locale=state.locale,
        spread_type=state.spread_type,
    )
    with observer.observe_step(
        step_name="draw_interpreter",
        as_type="chain",
        input_payload={"question": payload.question, "spread_type": payload.spread_type.value},
        metadata={"session_id": state.session_id, "reading_id": state.reading_id},
    ) as observation:
        for attempt_no in (1, 2):
            started = perf_counter()
            try:
                draw_output = draw_agent.run(payload)
                state.draw_output = draw_output
                state.cards = draw_output.cards
                state.status = WorkflowStatus.DRAW_COMPLETED
                state.trace_events.append(
                    trace_event_factory(
                        step_name="draw_interpreter",
                        event_status=TraceEventStatus.SUCCEEDED,
                        attempt_no=attempt_no,
                        started=started,
                        payload={"card_count": len(draw_output.cards)},
                    )
                )
                observation.success(output={"card_count": len(draw_output.cards)})
                trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
                return state
            except Exception as exc:  # pragma: no cover - exercised by backend tests
                state.trace_events.append(
                    trace_event_factory(
                        step_name="draw_interpreter",
                        event_status=TraceEventStatus.FAILED,
                        attempt_no=attempt_no,
                        started=started,
                        error_code="SCHEMA_VALIDATION_FAILED",
                        payload={
                            "reason": f"draw_interpreter execution failed: {exc}",
                            "exception_type": type(exc).__name__,
                        },
                    )
                )
                observation.failure(
                    error_code="SCHEMA_VALIDATION_FAILED",
                    message="Draw interpreter attempt failed.",
                    metadata={"attempt_no": attempt_no, "exception_type": type(exc).__name__},
                )
                trace_logger(state=state, reading_id=state.reading_id, only_latest=True)

    state.trace_events.append(
        trace_event_factory(
            step_name="draw_interpreter",
            event_status=TraceEventStatus.FALLBACK,
            attempt_no=3,
            started=None,
            error_code="STEP_FALLBACK_TRIGGERED",
            payload={"reason": "draw_interpreter exhausted retries"},
        )
    )
    state.completed_at = datetime.now(UTC)
    state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
    state.safety_output = protective_fallback_factory(
        review_notes="Draw interpreter failed repeatedly; returned a protective fallback output."
    )
    trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
    return state
