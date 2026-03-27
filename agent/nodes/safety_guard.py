"""Safety Guard Agent node stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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


async def safety_guard_node(state: OrchestratorState) -> OrchestratorState:
    """Run policy checks and rewrite risky outputs if needed.

    TODO:
        - evaluate SynthesisOutput against policy rules
        - call dedicated safety prompt/model when required
        - emit SafetyReport with remediation steps
        - persist audit trail hooks for Langfuse + JSON logs
    """

    raise NotImplementedError("Safety Guard node logic is pending implementation")
