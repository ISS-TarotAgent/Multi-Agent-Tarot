"""Tests for the synthesis node (execute_synthesis_step)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from agent.nodes.synthesis import execute_synthesis_step
from agent.schemas.draw import DrawCard
from agent.schemas.safety import SafetyReviewOutput
from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from backend.app.domain.enums import (
    CardOrientation,
    CardPosition,
    RiskLevel,
    SafetyAction,
    SpreadType,
    TraceEventStatus,
    WorkflowStatus,
)
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_INTERPRETATIONS = ["Past: potential.", "Present: challenge.", "Future: growth."]
_POSITIONS = [CardPosition.PAST, CardPosition.PRESENT, CardPosition.FUTURE]


def _make_cards(interpretations: list[str] = _INTERPRETATIONS) -> list[DrawCard]:
    return [
        DrawCard(
            position=pos,
            card_code=f"card_{i}",
            card_name=f"Card {i}",
            orientation=CardOrientation.UPRIGHT,
            interpretation=text,
        )
        for i, (pos, text) in enumerate(zip(_POSITIONS, interpretations), 1)
    ]


def _make_state(**overrides) -> TarotWorkflowState:
    defaults: dict[str, Any] = dict(
        session_id="sess-1",
        reading_id="read-1",
        raw_question="How can I grow?",
        normalized_question="How can I grow?",
        locale="en",
        spread_type=SpreadType.THREE_CARD_REFLECTION,
        cards=_make_cards(),
        status=WorkflowStatus.DRAW_COMPLETED,
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return TarotWorkflowState(**defaults)


def _noop_trace_event_factory(
    *,
    step_name: str,
    event_status: TraceEventStatus,
    attempt_no: int,
    payload: dict[str, Any],
    started: float | None,
    error_code: str | None = None,
) -> TraceEventPayload:
    return TraceEventPayload(
        event_id="test-event-id",
        step_name=step_name,
        event_status=event_status,
        attempt_no=attempt_no,
        payload=payload,
        created_at=datetime.now(UTC),
    )


def _make_observer() -> tuple[MagicMock, MagicMock]:
    handle = MagicMock()
    observer = MagicMock()

    @contextmanager
    def _observe(**_kwargs):
        yield handle

    observer.observe_step.side_effect = _observe
    return observer, handle


def _make_synthesis_output() -> SynthesisOutput:
    return SynthesisOutput(
        summary="The cards reveal a path of transformation.",
        action_advice="Take one step at a time.",
        reflection_question="What does growth mean to you?",
    )


def _make_fallback() -> SafetyReviewOutput:
    return SafetyReviewOutput(
        risk_level=RiskLevel.HIGH,
        action_taken=SafetyAction.BLOCK_AND_FALLBACK,
        review_notes="fallback",
        safe_summary="safe",
        safe_action_advice="safe advice",
        safe_reflection_question="safe question",
    )


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_execute_synthesis_step_success():
    state = _make_state()
    observer, handle = _make_observer()
    synthesis_agent = MagicMock()
    synthesis_agent.run.return_value = _make_synthesis_output()

    result = execute_synthesis_step(
        state=state,
        synthesis_agent=synthesis_agent,
        observer=observer,
        trace_event_factory=_noop_trace_event_factory,
        trace_logger=MagicMock(),
        protective_fallback_factory=MagicMock(return_value=_make_fallback()),
    )

    assert result.status is WorkflowStatus.SYNTHESIS_COMPLETED
    assert result.synthesis_output is not None
    assert "transformation" in result.synthesis_output.summary
    synthesis_agent.run.assert_called_once()
    handle.success.assert_called_once()


def test_execute_synthesis_step_builds_correct_payload():
    state = _make_state()
    observer, _ = _make_observer()
    synthesis_agent = MagicMock()
    synthesis_agent.run.return_value = _make_synthesis_output()

    execute_synthesis_step(
        state=state,
        synthesis_agent=synthesis_agent,
        observer=observer,
        trace_event_factory=_noop_trace_event_factory,
        trace_logger=MagicMock(),
        protective_fallback_factory=MagicMock(return_value=_make_fallback()),
    )

    called_payload: SynthesisInput = synthesis_agent.run.call_args[0][0]
    assert called_payload.normalized_question == "How can I grow?"
    assert called_payload.locale == "en"
    assert len(called_payload.card_interpretations) == 3
    assert "Past: potential." in called_payload.card_interpretations


# ---------------------------------------------------------------------------
# Retry path
# ---------------------------------------------------------------------------


def test_execute_synthesis_step_succeeds_on_second_attempt():
    state = _make_state()
    observer, handle = _make_observer()
    synthesis_agent = MagicMock()
    synthesis_agent.run.side_effect = [RuntimeError("transient error"), _make_synthesis_output()]

    result = execute_synthesis_step(
        state=state,
        synthesis_agent=synthesis_agent,
        observer=observer,
        trace_event_factory=_noop_trace_event_factory,
        trace_logger=MagicMock(),
        protective_fallback_factory=MagicMock(return_value=_make_fallback()),
    )

    assert result.status is WorkflowStatus.SYNTHESIS_COMPLETED
    assert synthesis_agent.run.call_count == 2
    handle.success.assert_called_once()


# ---------------------------------------------------------------------------
# Fallback path
# ---------------------------------------------------------------------------


def test_execute_synthesis_step_fallback_after_all_attempts_fail():
    state = _make_state()
    observer, handle = _make_observer()
    synthesis_agent = MagicMock()
    synthesis_agent.run.side_effect = RuntimeError("persistent error")
    fallback = _make_fallback()

    result = execute_synthesis_step(
        state=state,
        synthesis_agent=synthesis_agent,
        observer=observer,
        trace_event_factory=_noop_trace_event_factory,
        trace_logger=MagicMock(),
        protective_fallback_factory=MagicMock(return_value=fallback),
    )

    assert result.status is WorkflowStatus.SAFE_FALLBACK_RETURNED
    assert result.safety_output is fallback
    assert result.synthesis_output is None
    assert synthesis_agent.run.call_count == 2
    handle.failure.assert_called()


def test_execute_synthesis_step_trace_events_recorded_on_failure():
    state = _make_state()
    observer, _ = _make_observer()
    synthesis_agent = MagicMock()
    synthesis_agent.run.side_effect = RuntimeError("error")

    trace_calls: list[dict[str, Any]] = []

    def capture_trace(**kwargs: Any) -> TraceEventPayload:
        trace_calls.append(kwargs)
        return _noop_trace_event_factory(**kwargs)

    execute_synthesis_step(
        state=state,
        synthesis_agent=synthesis_agent,
        observer=observer,
        trace_event_factory=capture_trace,
        trace_logger=MagicMock(),
        protective_fallback_factory=MagicMock(return_value=_make_fallback()),
    )

    statuses = [c["event_status"] for c in trace_calls]
    assert TraceEventStatus.FAILED in statuses
    assert TraceEventStatus.FALLBACK in statuses


# ---------------------------------------------------------------------------
# normalized_question fallback to raw_question
# ---------------------------------------------------------------------------


def test_execute_synthesis_step_falls_back_to_raw_question():
    state = _make_state(normalized_question=None)
    observer, _ = _make_observer()
    synthesis_agent = MagicMock()
    synthesis_agent.run.return_value = _make_synthesis_output()

    execute_synthesis_step(
        state=state,
        synthesis_agent=synthesis_agent,
        observer=observer,
        trace_event_factory=_noop_trace_event_factory,
        trace_logger=MagicMock(),
        protective_fallback_factory=MagicMock(return_value=_make_fallback()),
    )

    called_payload: SynthesisInput = synthesis_agent.run.call_args[0][0]
    assert called_payload.normalized_question == "How can I grow?"
