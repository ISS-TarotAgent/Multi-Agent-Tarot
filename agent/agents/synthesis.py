from __future__ import annotations

from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from app.domain.enums import CardPosition


class SynthesisAgent:
    """Combines the draw result into a concise reflection summary."""

    _POSITION_LABELS = {
        CardPosition.PAST: "过去",
        CardPosition.PRESENT: "现在",
        CardPosition.FUTURE: "未来",
    }

    def run(self, payload: SynthesisInput) -> SynthesisOutput:
        card_map = {card.position: card for card in payload.cards}
        past = card_map[CardPosition.PAST]
        present = card_map[CardPosition.PRESENT]
        future = card_map[CardPosition.FUTURE]

        summary = (
            f"围绕“{payload.normalized_question}”，这组三张牌显示你正从 {past.card_name} 所代表的旧经验中走出，"
            f"当前重点落在 {present.card_name} 提醒的现实抉择，而未来更需要吸收 {future.card_name} 带来的节奏与方向感。"
        )
        action_advice = (
            f"先把与 {present.card_name} 对应的一项现实行动拆成最小一步，再用一周时间观察它是否真的让你更靠近想要的状态。"
        )
        reflection_question = (
            f"如果你不再急着一次做出最终决定，{future.card_name} 所代表的品质最值得你现在先练习哪一部分？"
        )
        return SynthesisOutput(
            summary=summary,
            action_advice=action_advice,
            reflection_question=reflection_question,
        )
