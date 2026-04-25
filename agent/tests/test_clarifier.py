"""Unit tests for execute_clarifier_step in agent/nodes/clarifier.py.

All tests use mock ClarifierAgent implementations — no real LLM calls are made.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from agent.nodes.clarifier import execute_clarifier_step
from agent.schemas.clarifier import (
    ClarificationPrompt,
    ClarifierFinalizeInput,
    ClarifierFinalizeOutput,
    ClarifierInput,
    ClarifierOutput,
)
from agent.schemas.safety import SafetyReviewOutput
from backend.app.domain.enums import (
    RiskLevel,
    SafetyAction,
    SpreadType,
    TraceEventStatus,
    WorkflowStatus,
)
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload

# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _make_state(
    status: WorkflowStatus = WorkflowStatus.QUESTION_RECEIVED,
    raw_question: str = "我最近工作不顺，该怎么办？",
    normalized_question: str | None = None,
    intent_tag: str | None = None,
    clarification_answers: dict[str, str] | None = None,
    skip_clarification: bool = False,
) -> TarotWorkflowState:
    return TarotWorkflowState(
        session_id="test-session",
        reading_id="test-reading",
        status=status,
        locale="zh-CN",
        spread_type=SpreadType.THREE_CARD_REFLECTION,
        raw_question=raw_question,
        normalized_question=normalized_question,
        intent_tag=intent_tag,
        clarification_answers=clarification_answers or {},
        skip_clarification=skip_clarification,
        created_at=datetime.now(UTC),
    )


def _noop_trace_event(
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


def _noop_trace_logger(*, state: TarotWorkflowState, reading_id: str | None, only_latest: bool = False) -> None:
    pass


def _noop_fallback(*, review_notes: str) -> SafetyReviewOutput:
    return SafetyReviewOutput(
        risk_level=RiskLevel.HIGH,
        action_taken=SafetyAction.BLOCK_AND_FALLBACK,
        review_notes=review_notes,
        safe_summary="",
        safe_action_advice="",
        safe_reflection_question="",
    )


class _NoOpObserver:
    @contextmanager
    def observe_step(self, *, step_name, as_type, input_payload=None, metadata=None):
        yield _NoOpHandle()


class _NoOpHandle:
    def success(self, *, output=None, metadata=None) -> None:
        pass

    def failure(self, *, error_code=None, message="", metadata=None) -> None:
        pass


_OBSERVER = _NoOpObserver()

_VALID_RUN_OUTPUT = ClarifierOutput(
    normalized_question="我在职场中遇到了困难，应该如何应对？",
    intent_tag="career",
    clarification_required=True,
    clarifier_question="你目前在职场上面临的主要挑战是什么？",
    clarification_prompts=[
        ClarificationPrompt(
            id="q1",
            question="你目前在职场上面临的主要挑战是什么？",
            helper_text="了解当前处境有助于塔罗牌更准确地指引职业方向。",
            placeholder="例如：是否要接受一个新的工作机会",
        ),
        ClarificationPrompt(
            id="q2",
            question="你希望这次塔罗解读聚焦于哪个时间范围？",
            helper_text="时间范围帮助塔罗牌定位能量走向。",
            placeholder="例如：未来三个月内",
        ),
    ],
)

_VALID_FINALIZE_OUTPUT = ClarifierFinalizeOutput(
    reframed_question="在职业发展的十字路口，我如何找到与内心价值对齐的方向？",
    topic="职业发展与决策",
    time_horizon="未来三个月",
    intent="寻求职业发展方向的内在洞察",
    constraints=["关注实际行动步骤"],
)


class _MockClarifierAgent:
    def __init__(
        self,
        run_output: ClarifierOutput = _VALID_RUN_OUTPUT,
        finalize_output: ClarifierFinalizeOutput = _VALID_FINALIZE_OUTPUT,
        run_raises: Exception | None = None,
        finalize_raises: Exception | None = None,
    ):
        self._run_output = run_output
        self._finalize_output = finalize_output
        self._run_raises = run_raises
        self._finalize_raises = finalize_raises
        self.run_call_count = 0
        self.finalize_call_count = 0

    def run(self, payload: ClarifierInput) -> ClarifierOutput:
        self.run_call_count += 1
        if self._run_raises:
            raise self._run_raises
        return self._run_output

    def finalize(self, payload: ClarifierFinalizeInput) -> ClarifierFinalizeOutput:
        self.finalize_call_count += 1
        if self._finalize_raises:
            raise self._finalize_raises
        return self._finalize_output


def _run(state: TarotWorkflowState, agent: _MockClarifierAgent) -> TarotWorkflowState:
    return execute_clarifier_step(
        state=state,
        clarifier_agent=agent,
        observer=_OBSERVER,
        trace_event_factory=_noop_trace_event,
        trace_logger=_noop_trace_logger,
    )


# ---------------------------------------------------------------------------
# Phase 1 tests: initial clarification question generation
# ---------------------------------------------------------------------------


def test_phase1_requires_clarification_produces_clarifying_status():
    """When LLM says clarification required, state becomes CLARIFYING."""
    state = _make_state()
    agent = _MockClarifierAgent()

    result = _run(state, agent)

    assert result.status is WorkflowStatus.CLARIFYING
    assert result.normalized_question == "我在职场中遇到了困难，应该如何应对？"
    assert result.intent_tag == "career"
    assert len(result.clarification_prompts) == 2
    assert agent.run_call_count == 1
    assert agent.finalize_call_count == 0


def test_phase1_no_clarification_needed_chains_to_finalize():
    """When clarification is not required, Phase 1 chains directly into Phase 2."""
    no_clarif = ClarifierOutput(
        normalized_question="我在职场遇到困难",
        intent_tag="career",
        clarification_required=False,
    )
    agent = _MockClarifierAgent(run_output=no_clarif)
    state = _make_state()

    result = _run(state, agent)

    assert result.status is WorkflowStatus.READY_FOR_DRAW
    assert result.normalized_question == _VALID_FINALIZE_OUTPUT.reframed_question
    assert agent.run_call_count == 1
    assert agent.finalize_call_count == 1


def test_phase1_skip_clarification_flag_bypasses_clarification():
    """skip_clarification=True skips waiting for answers and chains to Phase 2 directly."""
    agent = _MockClarifierAgent()
    state = _make_state(skip_clarification=True)

    result = _run(state, agent)

    assert result.status is WorkflowStatus.READY_FOR_DRAW
    assert agent.finalize_call_count == 1


def test_phase1_intent_tag_stored_in_state():
    """Intent tag from Phase 1 is propagated into the state."""
    agent = _MockClarifierAgent()
    state = _make_state()
    result = _run(state, agent)
    assert result.intent_tag == "career"


def test_phase1_agent_failure_falls_back_to_raw_question():
    """When the agent raises, state falls back to raw question and is READY_FOR_DRAW."""
    agent = _MockClarifierAgent(run_raises=RuntimeError("LLM down"))
    state = _make_state()

    result = _run(state, agent)

    assert result.status is WorkflowStatus.READY_FOR_DRAW
    assert result.normalized_question == state.raw_question
    assert len(result.trace_events) == 1
    assert result.trace_events[0].event_status is TraceEventStatus.FALLBACK


# ---------------------------------------------------------------------------
# Phase 2 tests: finalization with clarification answers
# ---------------------------------------------------------------------------


def test_phase2_resume_with_answers_produces_ready_state():
    """When state is CLARIFYING with answers, Phase 2 runs and produces READY_FOR_DRAW."""
    agent = _MockClarifierAgent()
    state = _make_state(
        status=WorkflowStatus.CLARIFYING,
        normalized_question="我在职场中遇到了困难，应该如何应对？",
        intent_tag="career",
        clarification_answers={"q1": "我想了解职业方向的选择"},
    )

    result = _run(state, agent)

    assert result.status is WorkflowStatus.READY_FOR_DRAW
    assert result.normalized_question == _VALID_FINALIZE_OUTPUT.reframed_question
    assert agent.run_call_count == 0
    assert agent.finalize_call_count == 1


def test_phase2_finalize_failure_falls_back_to_raw_question():
    """When finalize raises, the node falls back to raw_question and is still READY_FOR_DRAW."""
    agent = _MockClarifierAgent(finalize_raises=RuntimeError("API unreachable"))
    raw = "我最近工作不顺，该怎么办？"
    state = _make_state(
        status=WorkflowStatus.CLARIFYING,
        raw_question=raw,
        normalized_question="我在职场遇到困难",
        intent_tag="career",
        clarification_answers={"q1": "some answer"},
    )

    result = _run(state, agent)

    assert result.status is WorkflowStatus.READY_FOR_DRAW
    # fallback overwrites normalized_question with raw_question (effective_question or raw_question)
    assert result.normalized_question == raw


def test_phase2_uses_existing_intent_tag_from_state():
    """Phase 2 reads intent_tag from state, not from agent.run()."""
    agent = _MockClarifierAgent()
    state = _make_state(
        status=WorkflowStatus.CLARIFYING,
        normalized_question="关系问题",
        intent_tag="relationship",
        clarification_answers={"q1": "我和伴侣关系出现了问题"},
    )

    _run(state, agent)

    assert agent.run_call_count == 0
    assert agent.finalize_call_count == 1


# ---------------------------------------------------------------------------
# Trace event tests
# ---------------------------------------------------------------------------


def test_trace_event_recorded_on_success():
    """A single SUCCEEDED trace event is appended on a normal Phase 1 call."""
    agent = _MockClarifierAgent()
    state = _make_state()
    result = _run(state, agent)
    assert len(result.trace_events) == 1
    assert result.trace_events[0].event_status is TraceEventStatus.SUCCEEDED
    assert result.trace_events[0].step_name == "clarifier"


def test_trace_event_payload_contains_phase():
    """Trace event payload includes a 'phase' key identifying the execution path."""
    agent = _MockClarifierAgent()
    state = _make_state()
    result = _run(state, agent)
    assert "phase" in result.trace_events[0].payload


# ---------------------------------------------------------------------------
# Intent tag validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("intent_tag", ["career", "relationship", "study", "emotion", "growth"])
def test_all_valid_intent_tags_accepted(intent_tag: str):
    """Every valid intent tag can be stored in ClarifierOutput."""
    output = ClarifierOutput(
        normalized_question="test",
        intent_tag=intent_tag,
        clarification_required=False,
    )
    assert output.intent_tag == intent_tag
