"""Synthesis node for combining card interpretations into structured reflection."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol

from agent.schemas.safety import SafetyReviewOutput
from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from backend.app.domain.enums import TraceEventStatus, WorkflowStatus
from backend.app.schemas.workflow import TarotWorkflowState


class SynthesisAgent(Protocol):
    def run(self, payload: SynthesisInput) -> SynthesisOutput: ...


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
    ) -> Any: ...


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


def execute_synthesis_step(
    *,
    state: TarotWorkflowState,
    synthesis_agent: SynthesisAgent,
    observer: WorkflowObserver,
    trace_event_factory: TraceEventFactory,
    trace_logger: TraceLogger,
    protective_fallback_factory: ProtectiveFallbackFactory,
) -> TarotWorkflowState:
    payload = SynthesisInput(
        normalized_question=state.normalized_question or state.raw_question,
        card_interpretations=[card.interpretation for card in state.cards],
        locale=state.locale,
    )
    with observer.observe_step(
        step_name="synthesis",
        as_type="chain",
        input_payload={"card_count": len(state.cards)},
        metadata={"session_id": state.session_id, "reading_id": state.reading_id},
    ) as observation:
        for attempt_no in (1, 2):
            started = perf_counter()
            try:
                synthesis_output = synthesis_agent.run(payload)
                state.synthesis_output = synthesis_output
                state.status = WorkflowStatus.SYNTHESIS_COMPLETED
                state.trace_events.append(
                    trace_event_factory(
                        step_name="synthesis",
                        event_status=TraceEventStatus.SUCCEEDED,
                        attempt_no=attempt_no,
                        started=started,
                        payload={"summary_length": len(synthesis_output.summary)},
                    )
                )
                observation.success(output={"summary_length": len(synthesis_output.summary)})
                trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
                return state
            except Exception as exc:
                state.trace_events.append(
                    trace_event_factory(
                        step_name="synthesis",
                        event_status=TraceEventStatus.FAILED,
                        attempt_no=attempt_no,
                        started=started,
                        error_code="SYNTHESIS_FAILED",
                        payload={
                            "reason": f"synthesis execution failed: {exc}",
                            "exception_type": type(exc).__name__,
                        },
                    )
                )
                observation.failure(
                    error_code="SYNTHESIS_FAILED",
                    message="Synthesis attempt failed.",
                    metadata={"attempt_no": attempt_no, "exception_type": type(exc).__name__},
                )
                trace_logger(state=state, reading_id=state.reading_id, only_latest=True)

    state.trace_events.append(
        trace_event_factory(
            step_name="synthesis",
            event_status=TraceEventStatus.FALLBACK,
            attempt_no=3,
            started=None,
            error_code="STEP_FALLBACK_TRIGGERED",
            payload={"reason": "synthesis exhausted retries"},
        )
    )
    state.completed_at = datetime.now(UTC)
    state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
    state.safety_output = protective_fallback_factory(
        review_notes="Synthesis failed repeatedly; returned a protective fallback output."
    )
    trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
    return state
