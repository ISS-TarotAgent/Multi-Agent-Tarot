from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from agent.schemas.draw import DrawCard, DrawInput, DrawOutput
from app.domain.enums import CardOrientation, CardPosition


class DrawInterpreterAgent:
    """Draws three deterministic cards and turns them into readable interpretations."""

    _POSITION_LABELS = {
        CardPosition.PAST: "过去",
        CardPosition.PRESENT: "现在",
        CardPosition.FUTURE: "未来",
    }

    def run(self, payload: DrawInput) -> DrawOutput:
        cards = self._load_cards()
        if len(cards) < 3:
            raise ValueError("tarot knowledge file must contain at least three cards.")

        selected_cards = self._select_cards(payload.normalized_question, cards)
        result_cards: list[DrawCard] = []

        for position, knowledge, orientation in selected_cards:
            meaning_key = "upright_meaning" if orientation is CardOrientation.UPRIGHT else "reversed_meaning"
            interpretation = (
                f"{self._POSITION_LABELS[position]}位置的{knowledge['name']}提示："
                f"{knowledge[meaning_key]}。它提醒你把注意力放回“{knowledge['theme']}”这个主题。"
            )
            result_cards.append(
                DrawCard(
                    position=position,
                    card_code=knowledge["code"],
                    card_name=knowledge["name"],
                    orientation=orientation,
                    interpretation=interpretation,
                )
            )

        draw_summary = "、".join(card.card_name for card in result_cards)
        return DrawOutput(
            cards=result_cards,
            draw_summary=f"本次三张牌分别是：{draw_summary}。",
        )

    def _select_cards(
        self,
        normalized_question: str,
        cards: list[dict[str, Any]],
    ) -> list[tuple[CardPosition, dict[str, Any], CardOrientation]]:
        seed = hashlib.sha256(normalized_question.encode("utf-8")).hexdigest()
        selected_indexes: list[int] = []
        offset = 0

        while len(selected_indexes) < 3:
            chunk = seed[offset : offset + 8]
            if len(chunk) < 8:
                seed += hashlib.sha256(f"{normalized_question}:{offset}".encode("utf-8")).hexdigest()
                continue
            index = int(chunk, 16) % len(cards)
            offset += 8
            if index not in selected_indexes:
                selected_indexes.append(index)

        positions = [CardPosition.PAST, CardPosition.PRESENT, CardPosition.FUTURE]
        results: list[tuple[CardPosition, dict[str, Any], CardOrientation]] = []
        for cursor, index in enumerate(selected_indexes):
            orientation_seed = int(seed[(offset + cursor * 2) : (offset + cursor * 2 + 2)] or "0", 16)
            orientation = CardOrientation.UPRIGHT if orientation_seed % 2 == 0 else CardOrientation.REVERSED
            results.append((positions[cursor], cards[index], orientation))
        return results

    @staticmethod
    @lru_cache
    def _load_cards() -> list[dict[str, Any]]:
        resource_path = Path(__file__).resolve().parents[1] / "resources" / "tarot_cards.yaml"
        with resource_path.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file)
        cards = payload.get("cards", [])
        if not isinstance(cards, list):
            raise ValueError("tarot_cards.yaml must contain a top-level 'cards' list.")
        return cards
