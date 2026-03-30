"""Safety Guard Agent node stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional,Any

from agent.core.schemas import RequiredAction, RiskLevel, SafetyDecision, TrustTaggedContent,OrchestratorState

@dataclass(slots=True)
class SafeFallbackResponse:
    message: str
    fallback_type: str
    should_ask_rephrase: bool = False
    metadata: dict | None = None

DEFAULT_BLOCK_MESSAGE = (
    "我暂时不能按当前这段请求继续处理."
    "你可以直接告诉我你想占卜的主题,如感情,学业,事业或关系,"
)

REPHRASE_MESSAGE = (
    "你的请求里包含了一些不便直接处理的内容."
    "请你换一种更直接,简洁的方式描述想问的问题,例如:'我想做一次关于感情的塔罗解读'"
)

HIGH_RISK_MESSAGE = (
    "这次请求我不能继续按原样处理."
    "如果你愿意,可以重新用一句简单的话说明你想咨询的主题,我会继续帮助你."
)


def build_safe_fallback_response(
        decision: Optional[SafetyDecision] = None,
) -> SafeFallbackResponse:
    """
    Build a safe fallback response when the workflow must stop or downgrade

    This function intentionally avoids exposing internal security rules,
    detecotr logic, or workflow details
    """
    if decision is None:
        return SafeFallbackResponse(
            message = DEFAULT_BLOCK_MESSAGE,
            fallback_type="default_block",
            should_ask_rephrase=True,
            metadata={"reason": "missing_decision"},
        )
    
    if decision.required_action == RequiredAction.ASK_CLARIFICATION:
        return SafeFallbackResponse(
            message = REPHRASE_MESSAGE,
            fallback_type="ask_rephrase",
            should_ask_rephrase=True,
            metadata={
                "risk_level": decision.risk_level.value,
                "detected_risks": decision.detected_risks
            },
        )
    
    if decision.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
        return SafeFallbackResponse(
            message = HIGH_RISK_MESSAGE,
            fallback_type="high_risk_block",
            should_ask_rephrase=True,
            metadata={
                "risk_level": decision.risk_level.value,
                "detected_risks": decision.detected_risks
            },
        )
    
    return SafeFallbackResponse(
        message = DEFAULT_BLOCK_MESSAGE,
        fallback_type="default_block",
        should_ask_rephrase=True,
        metadata={
            "risk_level": decision.risk_level.value,
            "detected_risks": decision.detected_risks
        },
    )

def safe_fallback_node(
    decision: Optional[SafetyDecision] = None,
) -> dict[str,Any]:
    """
    Node-style wrapper for workflow integration,
    Returns a simple dict so it can be easily consumed by orchestrators.
    """
    fallback = build_safe_fallback_response(decision)

    return {
        "status":"safe_fallback",
        "final_response":fallback.message,
        "fallback_type":fallback.fallback_type,
        "should_ask_rephrase":fallback.should_ask_rephrase,
        "metadata":fallback.metadata or {},
    }
    
async def safety_guard_node(state: OrchestratorState) -> OrchestratorState:
    """Run policy checks and rewrite risky outputs if needed.

    TODO:
        - evaluate SynthesisOutput against policy rules
        - call dedicated safety prompt/model when required
        - emit SafetyReport with remediation steps
        - persist audit trail hooks for Langfuse + JSON logs
    """

    raise NotImplementedError("Safety Guard node logic is pending implementation")
