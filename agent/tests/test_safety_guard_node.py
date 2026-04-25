"""Unit tests for execute_safety_guard_step in agent/nodes/safety_guard.py."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from agent.nodes.safety_guard import execute_safety_guard_step
from agent.schemas.safety import SafetyReviewOutput
from agent.schemas.synthesis import SynthesisOutput
from backend.app.domain.enums import (
    RiskLevel,
    SafetyAction,
    SpreadType,
    TraceEventStatus,
    WorkflowStatus,
)
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_state(
    summary: str = "",
    action_advice: str = "",
    reflection_question: str = "",
    synthesis_output: SynthesisOutput | None = None,
) -> TarotWorkflowState:
    if synthesis_output is None and (summary or action_advice or reflection_question):
        synthesis_output = SynthesisOutput(
            summary=summary,
            action_advice=action_advice,
            reflection_question=reflection_question,
        )
    return TarotWorkflowState(
        session_id="test-session",
        reading_id="test-reading",
        status=WorkflowStatus.SYNTHESIS_COMPLETED,
        locale="zh-CN",
        spread_type=SpreadType.THREE_CARD_REFLECTION,
        raw_question="测试问题",
        synthesis_output=synthesis_output,
        created_at=datetime.now(UTC),
    )


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


def _noop_trace_logger(*, state: TarotWorkflowState, reading_id: str | None, only_latest: bool = False) -> None:
    pass


def _noop_protective_fallback(*, review_notes: str) -> SafetyReviewOutput:
    return SafetyReviewOutput(
        risk_level=RiskLevel.HIGH,
        action_taken=SafetyAction.BLOCK_AND_FALLBACK,
        review_notes=review_notes,
        safe_summary="Protective fallback.",
        safe_action_advice="",
        safe_reflection_question="",
    )


class _NoOpObservationHandle:
    def success(self, *, output=None, metadata=None) -> None:
        pass

    def failure(self, *, error_code, message, metadata=None) -> None:
        pass


class _NoOpObserver:
    @contextmanager
    def observe_step(self, *, step_name, as_type, input_payload=None, metadata=None):
        yield _NoOpObservationHandle()


def _run(state: TarotWorkflowState) -> TarotWorkflowState:
    return execute_safety_guard_step(
        state=state,
        observer=_NoOpObserver(),
        trace_event_factory=_noop_trace_event_factory,
        trace_logger=_noop_trace_logger,
        protective_fallback_factory=_noop_protective_fallback,
    )


# ---------------------------------------------------------------------------
# PASSTHROUGH — safe content
# ---------------------------------------------------------------------------


class TestPassthrough:
    def test_safe_content_passes_through(self):
        state = _make_state(
            summary="这张牌提示你关注当下的情绪状态。",
            action_advice="先把手头一件事做完，观察一周的变化。",
            reflection_question="如果只做一件事，你最想先确认哪个方向？",
        )
        result = _run(state)
        assert result.safety_output is not None
        assert result.safety_output.action_taken == SafetyAction.PASSTHROUGH

    def test_passthrough_risk_level_is_low(self):
        state = _make_state(
            summary="感情方面适合先沉淀。",
            action_advice="给自己一些独处时间。",
            reflection_question="你真正想要的是什么？",
        )
        result = _run(state)
        assert result.safety_output.risk_level == RiskLevel.LOW

    def test_passthrough_preserves_original_content(self):
        original_summary = "这是一段安全的塔罗综合建议。"
        state = _make_state(
            summary=original_summary,
            action_advice="继续保持当前节奏。",
            reflection_question="下一步你最想做什么？",
        )
        result = _run(state)
        assert result.safety_output.safe_summary == original_summary

    def test_passthrough_review_notes_is_none(self):
        state = _make_state(
            summary="事业方面适合主动出击。",
            action_advice="本周联系一个潜在合作伙伴。",
            reflection_question="谁是你信任且愿意合作的人？",
        )
        result = _run(state)
        assert result.safety_output.review_notes is None

    def test_passthrough_sets_completed_status(self):
        state = _make_state(
            summary="这张牌提示稳定前行。",
            action_advice="保持节奏。",
            reflection_question="下一步是什么？",
        )
        result = _run(state)
        assert result.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# REWRITE — medium-risk professional domains
# ---------------------------------------------------------------------------


class TestRewrite:
    def test_investment_keyword_triggers_rewrite(self):
        state = _make_state(
            summary="这次解读显示投资时机正在来临。",
            action_advice="可以考虑进行一些投资布局。",
            reflection_question="你对财务安全的真实态度是什么？",
        )
        result = _run(state)
        assert result.safety_output.action_taken == SafetyAction.REWRITE

    def test_medical_keyword_triggers_rewrite(self):
        state = _make_state(
            summary="牌面提示你的手术可能会顺利进行。",
            action_advice="先做好充分准备。",
            reflection_question="你对这次手术有什么担心？",
        )
        result = _run(state)
        assert result.safety_output.action_taken == SafetyAction.REWRITE

    def test_rewrite_risk_level_is_medium(self):
        state = _make_state(
            summary="炒股方面近期能量较强。",
            action_advice="可以考虑适当操作。",
            reflection_question="你对风险的接受程度如何？",
        )
        result = _run(state)
        assert result.safety_output.risk_level == RiskLevel.MEDIUM

    def test_rewrite_appends_disclaimer_to_summary(self):
        original = "牌面提示离婚后情绪将逐渐平稳。"
        state = _make_state(
            summary=original,
            action_advice="给自己时间适应新生活。",
            reflection_question="你现在最需要的支持是什么？",
        )
        result = _run(state)
        assert result.safety_output.safe_summary.startswith(original)
        assert len(result.safety_output.safe_summary) > len(original)

    def test_rewrite_reflection_question_unchanged(self):
        original_question = "你对这段关系的期待是什么？"
        state = _make_state(
            summary="官司方面有利的信号正在出现。",
            action_advice="保持冷静等待结果。",
            reflection_question=original_question,
        )
        result = _run(state)
        assert result.safety_output.safe_reflection_question == original_question

    def test_rewrite_sets_completed_status(self):
        state = _make_state(
            summary="投资方面需要谨慎。",
            action_advice="咨询专业人士。",
            reflection_question="你的风险承受能力如何？",
        )
        result = _run(state)
        assert result.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# BLOCK — high-risk self-harm / violence
# ---------------------------------------------------------------------------


class TestBlock:
    def test_self_harm_keyword_triggers_block(self):
        state = _make_state(
            summary="牌面能量显示你内心有不想活的想法需要正视。",
            action_advice="先停下来休息。",
            reflection_question="你还好吗？",
        )
        result = _run(state)
        assert result.safety_output.action_taken == SafetyAction.BLOCK_AND_FALLBACK

    def test_violence_keyword_triggers_block(self):
        state = _make_state(
            summary="关于伤害他人的冲动，牌面建议你先冷静。",
            action_advice="找专业人士倾诉。",
            reflection_question="你需要帮助吗？",
        )
        result = _run(state)
        assert result.safety_output.action_taken == SafetyAction.BLOCK_AND_FALLBACK

    def test_block_risk_level_is_high(self):
        state = _make_state(
            summary="涉及自杀念头的解读。",
            action_advice="需要帮助。",
            reflection_question="你现在安全吗？",
        )
        result = _run(state)
        assert result.safety_output.risk_level == RiskLevel.HIGH

    def test_block_replaces_content_with_protective_message(self):
        state = _make_state(
            summary="你提到了结束生命，这很令人担忧。",
            action_advice="暂时什么都不要做。",
            reflection_question="你有可以联系的人吗？",
        )
        result = _run(state)
        assert "结束生命" not in result.safety_output.safe_summary

    def test_block_has_review_notes(self):
        state = _make_state(
            summary="牌面围绕自杀意念展开。",
            action_advice="先寻求帮助。",
            reflection_question="下一步是什么？",
        )
        result = _run(state)
        assert result.safety_output.review_notes is not None

    def test_block_sets_safe_fallback_status(self):
        state = _make_state(
            summary="涉及暴力内容。",
            action_advice="冷静。",
            reflection_question="下一步？",
        )
        result = _run(state)
        assert result.status == WorkflowStatus.SAFE_FALLBACK_RETURNED


# ---------------------------------------------------------------------------
# Missing synthesis output (fallback)
# ---------------------------------------------------------------------------


class TestMissingSynthesis:
    def test_none_synthesis_returns_block(self):
        state = TarotWorkflowState(
            session_id="test-session",
            reading_id="test-reading",
            status=WorkflowStatus.SYNTHESIS_COMPLETED,
            locale="zh-CN",
            spread_type=SpreadType.THREE_CARD_REFLECTION,
            raw_question="测试",
            synthesis_output=None,
            created_at=datetime.now(UTC),
        )
        result = _run(state)
        assert result.safety_output is not None
        assert result.safety_output.action_taken == SafetyAction.BLOCK_AND_FALLBACK

    def test_none_synthesis_sets_safe_fallback_status(self):
        state = TarotWorkflowState(
            session_id="test-session",
            reading_id="test-reading",
            status=WorkflowStatus.SYNTHESIS_COMPLETED,
            locale="zh-CN",
            spread_type=SpreadType.THREE_CARD_REFLECTION,
            raw_question="测试",
            synthesis_output=None,
            created_at=datetime.now(UTC),
        )
        result = _run(state)
        assert result.status == WorkflowStatus.SAFE_FALLBACK_RETURNED

    def test_none_synthesis_review_notes_explains_reason(self):
        state = TarotWorkflowState(
            session_id="test-session",
            reading_id="test-reading",
            status=WorkflowStatus.SYNTHESIS_COMPLETED,
            locale="zh-CN",
            spread_type=SpreadType.THREE_CARD_REFLECTION,
            raw_question="测试",
            synthesis_output=None,
            created_at=datetime.now(UTC),
        )
        result = _run(state)
        assert result.safety_output.review_notes is not None
