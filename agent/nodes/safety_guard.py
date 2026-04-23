"""Safety Guard node and fallback utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Optional, Protocol

from agent.core.schemas import RequiredAction, SafetyDecision
from agent.schemas.safety import LLMSafetyCheckInput, SafetyReviewOutput
from backend.app.domain.enums import RiskLevel, SafetyAction, TraceEventStatus, WorkflowStatus
from backend.app.schemas.workflow import TarotWorkflowState


# ---------------------------------------------------------------------------
# Protocols (shared with other nodes)
# ---------------------------------------------------------------------------


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


class ObservationHandle(Protocol):
    def success(
        self, *, output: dict[str, object] | None = None, metadata: dict[str, object] | None = None
    ) -> None: ...
    def failure(self, *, error_code: str | None, message: str, metadata: dict[str, object] | None = None) -> None: ...


class WorkflowObserver(Protocol):
    def observe_step(
        self,
        *,
        step_name: str,
        as_type: str,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ): ...


class ProtectiveFallbackFactory(Protocol):
    def __call__(self, *, review_notes: str) -> SafetyReviewOutput: ...


class SafetyAgent(Protocol):
    def evaluate(self, payload: LLMSafetyCheckInput) -> Any: ...


# ---------------------------------------------------------------------------
# Safe fallback helpers (used by other nodes too)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SafeFallbackResponse:
    message: str
    fallback_type: str
    should_ask_rephrase: bool = False
    metadata: dict | None = None


DEFAULT_BLOCK_MESSAGE = "我暂时不能按当前这段请求继续处理.你可以直接告诉我你想占卜的主题,如感情,学业,事业或关系,"

REPHRASE_MESSAGE = (
    "你的请求里包含了一些不便直接处理的内容."
    "请你换一种更直接,简洁的方式描述想问的问题,例如:'我想做一次关于感情的塔罗解读'"
)

HIGH_RISK_MESSAGE = "这次请求我不能继续按原样处理.如果你愿意,可以重新用一句简单的话说明你想咨询的主题,我会继续帮助你."


def build_safe_fallback_response(
    decision: Optional[SafetyDecision] = None,
) -> SafeFallbackResponse:
    """Build a safe fallback response when the workflow must stop or downgrade.

    Intentionally avoids exposing internal detector logic or workflow details.
    """
    if decision is None:
        return SafeFallbackResponse(
            message=DEFAULT_BLOCK_MESSAGE,
            fallback_type="default_block",
            should_ask_rephrase=True,
            metadata={"reason": "missing_decision"},
        )

    if decision.required_action == RequiredAction.ASK_CLARIFICATION:
        return SafeFallbackResponse(
            message=REPHRASE_MESSAGE,
            fallback_type="ask_rephrase",
            should_ask_rephrase=True,
            metadata={
                "risk_level": decision.risk_level.value,
                "detected_risks": decision.detected_risks,
            },
        )

    if decision.risk_level == RiskLevel.HIGH:
        return SafeFallbackResponse(
            message=HIGH_RISK_MESSAGE,
            fallback_type="high_risk_block",
            should_ask_rephrase=True,
            metadata={
                "risk_level": decision.risk_level.value,
                "detected_risks": decision.detected_risks,
            },
        )

    return SafeFallbackResponse(
        message=DEFAULT_BLOCK_MESSAGE,
        fallback_type="default_block",
        should_ask_rephrase=True,
        metadata={
            "risk_level": decision.risk_level.value,
            "detected_risks": decision.detected_risks,
        },
    )


def safe_fallback_node(decision: Optional[SafetyDecision] = None) -> dict[str, Any]:
    """Node-style wrapper for workflow integration."""
    fallback = build_safe_fallback_response(decision)
    return {
        "status": "safe_fallback",
        "final_response": fallback.message,
        "fallback_type": fallback.fallback_type,
        "should_ask_rephrase": fallback.should_ask_rephrase,
        "metadata": fallback.metadata or {},
    }


# ---------------------------------------------------------------------------
# Keyword rule sets for output content policy
# ---------------------------------------------------------------------------

_HIGH_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        # 自伤 / 自杀
        "自杀",
        "自残",
        "不想活",
        "结束生命",
        "轻生",
        "去死",
        "想死",
        "割腕",
        "跳楼",
        "服药自尽",
        "了结自己",
        "活不下去",
        # 伤害他人
        "伤害他人",
        "杀人",
        "伤人",
        "杀死",
        "杀掉",
        "暴力",
        "报仇",
        "害人",
        "下毒",
        "投毒",
        # 英文高风险
        "suicide",
        "self-harm",
        "kill myself",
        "end my life",
        "kill someone",
        "hurt someone",
    }
)

_MEDIUM_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        # 金融投资
        "投资",
        "炒股",
        "股票",
        "基金",
        "理财",
        "期货",
        "加密货币",
        "比特币",
        "买房",
        "贷款",
        "债务",
        "破产",
        # 医疗健康
        "手术",
        "医疗",
        "诊断",
        "用药",
        "治疗",
        "化疗",
        "癌症",
        "病情",
        "病危",
        "急救",
        "药量",
        "剂量",
        # 法律纠纷
        "离婚",
        "官司",
        "诉讼",
        "律师",
        "判决",
        "仲裁",
        "起诉",
        "坐牢",
        "刑事",
        "犯罪",
        # 英文中风险
        "invest",
        "surgery",
        "diagnosis",
        "medication",
        "lawsuit",
        "divorce",
    }
)

_BLOCK_SAFE_SUMMARY = "这次解读我暂时无法继续提供。如果你正在经历困难，请联系身边信任的人或拨打心理援助热线。"

_REWRITE_DISCLAIMER = "\n\n*以上内容仅为塔罗牌象征性解读，不构成专业建议。如有实际需要，请咨询相关领域的专业人士。*"


def _scan(text: str, keywords: frozenset[str]) -> list[str]:
    return [kw for kw in keywords if kw in text]


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def execute_safety_guard_step(
    *,
    state: TarotWorkflowState,
    observer: WorkflowObserver,
    trace_event_factory: TraceEventFactory,
    trace_logger: TraceLogger,
    protective_fallback_factory: ProtectiveFallbackFactory,
    safety_agent: Optional[SafetyAgent] = None,
) -> TarotWorkflowState:
    """Check synthesis output against content policy and write SafetyReviewOutput.

    Flow:
    1. HIGH keyword hit → block immediately (rule-based, no LLM needed).
    2. MEDIUM keyword hit OR no keyword hit → LLM semantic evaluation when available.
    3. No LLM → fall back to rule-based MEDIUM/LOW classification.
    """
    with observer.observe_step(
        step_name="safety_guard",
        as_type="chain",
        input_payload={
            "has_synthesis": state.synthesis_output is not None,
            "llm_enabled": safety_agent is not None,
        },
        metadata={"session_id": state.session_id, "reading_id": state.reading_id},
    ) as observation:
        started = perf_counter()

        if state.synthesis_output is None:
            state.safety_output = protective_fallback_factory(
                review_notes="synthesis_output was None; cannot produce a safe reading."
            )
            state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
            state.completed_at = datetime.now(UTC)
            state.trace_events.append(
                trace_event_factory(
                    step_name="safety_guard",
                    event_status=TraceEventStatus.FALLBACK,
                    attempt_no=1,
                    started=started,
                    error_code="MISSING_SYNTHESIS",
                    payload={"reason": "synthesis_output is None"},
                )
            )
            observation.failure(
                error_code="MISSING_SYNTHESIS",
                message="synthesis_output was None.",
            )
            trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
            return state

        synth = state.synthesis_output
        scan_text = synth.summary + "\n" + synth.action_advice

        # --- Step 1: Rule-based HIGH risk — always block, never delegate to LLM ---
        high_hits = _scan(scan_text, _HIGH_RISK_KEYWORDS)
        if high_hits:
            state.safety_output = SafetyReviewOutput(
                risk_level=RiskLevel.HIGH,
                action_taken=SafetyAction.BLOCK_AND_FALLBACK,
                safe_summary=_BLOCK_SAFE_SUMMARY,
                safe_action_advice="",
                safe_reflection_question="",
                review_notes=f"高风险内容已拦截，命中关键词: {', '.join(high_hits)}",
            )
            state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
            state.completed_at = datetime.now(UTC)
            state.trace_events.append(
                trace_event_factory(
                    step_name="safety_guard",
                    event_status=TraceEventStatus.FALLBACK,
                    attempt_no=1,
                    started=started,
                    error_code="HIGH_RISK_CONTENT",
                    payload={"risk_level": "HIGH", "action_taken": "BLOCK_AND_FALLBACK", "method": "rules"},
                )
            )
            observation.failure(
                error_code="HIGH_RISK_CONTENT",
                message="High-risk content blocked by rules.",
                metadata={"hits": high_hits},
            )
            trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
            return state

        # --- Step 2: LLM semantic evaluation for MEDIUM keyword hits and clean content ---
        medium_hits = _scan(scan_text, _MEDIUM_RISK_KEYWORDS)

        if safety_agent is not None:
            try:
                llm_result = safety_agent.evaluate(
                    LLMSafetyCheckInput(
                        synthesis_text=scan_text,
                        question=state.raw_question or "",
                        keyword_hits=medium_hits,
                    )
                )
                effective_risk = llm_result.risk_level
                review_notes = f"LLM评估: {llm_result.reasoning}"
            except Exception:
                # LLM failure degrades gracefully to rule-based result
                effective_risk = "MEDIUM" if medium_hits else "LOW"
                review_notes = "LLM评估不可用，降级为规则判断"
        else:
            effective_risk = "MEDIUM" if medium_hits else "LOW"
            review_notes = None

        if effective_risk == "HIGH":
            state.safety_output = SafetyReviewOutput(
                risk_level=RiskLevel.HIGH,
                action_taken=SafetyAction.BLOCK_AND_FALLBACK,
                safe_summary=_BLOCK_SAFE_SUMMARY,
                safe_action_advice="",
                safe_reflection_question="",
                review_notes=review_notes,
            )
            state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
            state.completed_at = datetime.now(UTC)
            state.trace_events.append(
                trace_event_factory(
                    step_name="safety_guard",
                    event_status=TraceEventStatus.FALLBACK,
                    attempt_no=1,
                    started=started,
                    error_code="HIGH_RISK_CONTENT",
                    payload={"risk_level": "HIGH", "action_taken": "BLOCK_AND_FALLBACK", "method": "llm"},
                )
            )
            observation.failure(
                error_code="HIGH_RISK_CONTENT",
                message="High-risk content blocked by LLM.",
            )
            trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
            return state

        if effective_risk == "MEDIUM":
            state.safety_output = SafetyReviewOutput(
                risk_level=RiskLevel.MEDIUM,
                action_taken=SafetyAction.REWRITE,
                safe_summary=synth.summary + _REWRITE_DISCLAIMER,
                safe_action_advice=synth.action_advice + _REWRITE_DISCLAIMER,
                safe_reflection_question=synth.reflection_question,
                review_notes=review_notes,
            )
            state.status = WorkflowStatus.COMPLETED
            state.completed_at = datetime.now(UTC)
            state.trace_events.append(
                trace_event_factory(
                    step_name="safety_guard",
                    event_status=TraceEventStatus.SUCCEEDED,
                    attempt_no=1,
                    started=started,
                    payload={
                        "risk_level": "MEDIUM",
                        "action_taken": "REWRITE",
                        "method": "llm" if safety_agent is not None else "rules",
                    },
                )
            )
            observation.success(output={"risk_level": "MEDIUM", "action_taken": "REWRITE"})
            trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
            return state

        state.safety_output = SafetyReviewOutput(
            risk_level=RiskLevel.LOW,
            action_taken=SafetyAction.PASSTHROUGH,
            safe_summary=synth.summary,
            safe_action_advice=synth.action_advice,
            safe_reflection_question=synth.reflection_question,
            review_notes=review_notes,
        )
        state.status = WorkflowStatus.COMPLETED
        state.completed_at = datetime.now(UTC)
        state.trace_events.append(
            trace_event_factory(
                step_name="safety_guard",
                event_status=TraceEventStatus.SUCCEEDED,
                attempt_no=1,
                started=started,
                payload={
                    "risk_level": "LOW",
                    "action_taken": "PASSTHROUGH",
                    "method": "llm" if safety_agent is not None else "rules",
                },
            )
        )
        observation.success(output={"risk_level": "LOW", "action_taken": "PASSTHROUGH"})
    trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
    return state
