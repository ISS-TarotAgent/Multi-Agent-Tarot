from __future__ import annotations

from agent.schemas.safety import SafetyReviewInput, SafetyReviewOutput
from app.domain.enums import RiskLevel, SafetyAction


class SafetyGuardAgent:
    """Applies simple safety heuristics before a reading is returned to the user."""

    _HIGH_RISK_HINTS = ("自杀", "结束生命", "不想活", "伤害自己", "伤害他人", "杀人")
    _MEDIUM_RISK_HINTS = ("投资", "炒股", "手术", "诊断", "离婚", "官司", "贷款")

    def run(self, payload: SafetyReviewInput) -> SafetyReviewOutput:
        combined_text = " ".join(
            [
                payload.normalized_question,
                payload.summary,
                payload.action_advice,
                payload.reflection_question,
            ]
        )

        if any(keyword in combined_text for keyword in self._HIGH_RISK_HINTS):
            return SafetyReviewOutput(
                risk_level=RiskLevel.HIGH,
                action_taken=SafetyAction.BLOCK_AND_FALLBACK,
                safe_summary="你现在更需要的是被稳稳接住，而不是让任何占卜结果替你做危险决定。",
                safe_action_advice="请尽快联系你信任的人，或直接联系当地紧急援助与心理支持资源，先把安全放在第一位。",
                safe_reflection_question="此刻谁是你可以立刻联系、并且愿意陪你一起撑过这一段时间的人？",
                review_notes="Detected high-risk self-harm or violence related wording.",
            )

        if any(keyword in combined_text for keyword in self._MEDIUM_RISK_HINTS):
            return SafetyReviewOutput(
                risk_level=RiskLevel.MEDIUM,
                action_taken=SafetyAction.REWRITE,
                safe_summary=f"{payload.summary} 这更适合作为自我反思参考，不应替代医疗、法律或财务等专业判断。",
                safe_action_advice=f"{payload.action_advice} 在涉及重大现实决策时，请把专业意见放在更高优先级。",
                safe_reflection_question=payload.reflection_question,
                review_notes="Added professional-boundary disclaimer for a sensitive domain.",
            )

        return SafetyReviewOutput(
            risk_level=RiskLevel.LOW,
            action_taken=SafetyAction.PASSTHROUGH,
            safe_summary=payload.summary,
            safe_action_advice=payload.action_advice,
            safe_reflection_question=payload.reflection_question,
            review_notes=None,
        )
