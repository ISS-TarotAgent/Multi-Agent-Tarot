from __future__ import annotations

from agent.schemas.clarifier import ClarifierInput, ClarifierOutput


class ClarifierAgent:
    """Normalizes the user's question and flags when more context would help."""

    _AMBIGUOUS_HINTS = ("怎么办", "怎么做", "如何选", "该不该", "会怎样", "可以吗")
    _DOMAIN_HINTS = ("工作", "感情", "关系", "学习", "事业", "家庭", "选择", "转职", "合作")

    def run(self, payload: ClarifierInput) -> ClarifierOutput:
        raw_question = payload.raw_question.strip()
        clarification_required = self._needs_clarification(raw_question)

        if clarification_required:
            return ClarifierOutput(
                normalized_question=(
                    f"{raw_question}。在信息有限的情况下，优先聚焦当前最需要梳理的核心选择与下一步行动。"
                ),
                clarification_required=True,
                clarifier_question="你现在最想聚焦的是工作、关系、学习，还是个人状态？",
                confidence=0.42,
            )

        normalized_question = raw_question
        if not normalized_question.endswith(("？", "?")):
            normalized_question = f"{normalized_question}？"

        return ClarifierOutput(
            normalized_question=normalized_question,
            clarification_required=False,
            clarifier_question=None,
            confidence=0.88,
        )

    def _needs_clarification(self, raw_question: str) -> bool:
        if len(raw_question) < 12:
            return True
        if any(hint in raw_question for hint in self._AMBIGUOUS_HINTS) and not any(
            hint in raw_question for hint in self._DOMAIN_HINTS
        ):
            return True
        return False
