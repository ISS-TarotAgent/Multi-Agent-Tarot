from __future__ import annotations

import asyncio
import hashlib
import json
import random
import uuid
from textwrap import dedent
from typing import Any, Dict, List

from agent.core.prompt_registry import load_prompt
from agent.core.schemas import (
    CardInterpretation,
    DrawInterpretRequest,
    DrawInterpretResult,
    DrawInterpretTrace,
)
from agent.core.tarot_repository import TarotRepository
from agent.core.model_gateway import ModelInvocationContext


class TarotDrawService:
    PROMPT_NAME = "draw_interpret_system_prompt"
    PROMPT_VERSION = "v1"
    DECK_TYPE = "major_22"

    def __init__(self, repository: TarotRepository, model_gateway: Any) -> None:
        self.repository = repository
        self.model_gateway = model_gateway

    # ----------------------------
    # Seed + shuffle
    # ----------------------------
    @staticmethod
    def build_seed(session_id: str, question: str, spread_code: str, user_number: int) -> str:
        raw = f"{session_id}|{question.strip()}|{spread_code}|{user_number}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def shuffle_cards(cards: List[Dict[str, Any]], seed: str) -> List[Dict[str, Any]]:
        rng = random.Random(seed)
        deck = cards[:]
        rng.shuffle(deck)
        return deck

    @staticmethod
    def apply_orientation(cards: List[Dict[str, Any]], allow_reversed: bool, seed: str) -> List[Dict[str, Any]]:
        rng = random.Random(f"{seed}|orientation")
        result = []
        for card in cards:
            orientation = "upright"
            if allow_reversed:
                orientation = "reversed" if rng.choice([True, False]) else "upright"
            result.append({**card, "orientation": orientation})
        return result

    # ----------------------------
    # LLM调用（核心修改点）
    # ----------------------------
    async def _call_model_json(self, system_prompt: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 structured input 转成 prompt，然后调用 model_gateway.run()
        并解析 JSON 输出
        """

        user_json = json.dumps(payload, ensure_ascii=False)

        # 👇 拼接最终 prompt（非常关键）
        full_prompt = dedent(
            f"""
            {system_prompt}

            # Input
            {user_json}

            # Output
            请严格输出 JSON，不要包含任何解释或 markdown。
            """
        ).strip()

        # 调用 gateway
        result_text = self.model_gateway.run(
            full_prompt,
            context=ModelInvocationContext(
                metadata={
                    "prompt": self.PROMPT_NAME,
                    "version": self.PROMPT_VERSION,
                }
            ),
        )

        # 解析 JSON（带容错）
        try:
            return json.loads(result_text)
        except Exception:
            # fallback：尝试提取 JSON
            import re

            match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if match:
                return json.loads(match.group())

            raise ValueError(f"LLM output is not valid JSON:\n{result_text}")

    # ----------------------------
    # 单牌解释
    # ----------------------------
    async def interpret_single_card(
        self,
        *,
        question: str,
        spread_name: str,
        position_label: str,
        position_meaning: str,
        card_name_cn: str,
        card_name_en: str,
        orientation: str,
        keywords: List[str],
        core_meaning: str,
        advice: str,
        reflection_prompt: str,
    ) -> Dict[str, Any]:

        system_prompt = load_prompt(self.PROMPT_NAME)

        payload = {
            "question": question,
            "spread_name": spread_name,
            "position_label": position_label,
            "position_meaning": position_meaning,
            "card_name_cn": card_name_cn,
            "card_name_en": card_name_en,
            "orientation": orientation,
            "keywords": keywords,
            "core_meaning": core_meaning,
            "advice": advice,
            "reflection_prompt": reflection_prompt,
        }

        response = await self._call_model_json(system_prompt, payload)

        # basic校验
        for k in ["position_interpretation", "reflection_question", "caution_note"]:
            if k not in response:
                raise ValueError(f"Missing field: {k}")

        if "keywords" not in response:
            response["keywords"] = keywords

        return response

    # ----------------------------
    # 主流程
    # ----------------------------
    async def execute(self, request: DrawInterpretRequest) -> DrawInterpretResult:
        spread = self.repository.get_spread_by_code(request.spread_code)
        if not spread:
            raise ValueError(f"Spread not found: {request.spread_code}")

        positions = self.repository.get_spread_positions(spread["id"])

        session_id = request.session_id or f"sess_{uuid.uuid4().hex[:12]}"
        draw_id = f"draw_{uuid.uuid4().hex[:12]}"

        session_row_id = self.repository.create_tarot_session(
            session_id=session_id,
            user_question=request.question,
            spread_id=spread["id"],
            user_number=request.user_number,
            allow_reversed=request.allow_reversed,
        )

        seed = self.build_seed(
            session_id=session_id,
            question=request.question,
            spread_code=request.spread_code,
            user_number=request.user_number,
        )

        cards = self.repository.list_active_major_arcana_cards()
        shuffled = self.shuffle_cards(cards, seed)
        selected = shuffled[: spread["card_count"]]
        selected = self.apply_orientation(selected, request.allow_reversed, seed)

        draw_row_id = self.repository.create_draw(
            tarot_session_id=session_row_id,
            draw_id=draw_id,
            seed_value=seed,
            deck_type=self.DECK_TYPE,
            prompt_version=self.PROMPT_VERSION,
            model_name="unknown",
        )

        results: List[CardInterpretation] = []

        for idx, card in enumerate(selected):
            pos = positions[idx]

            meaning = self.repository.get_card_meaning(
                card_id=card["id"],
                orientation=card["orientation"],
            )

            llm_json = await self.interpret_single_card(
                question=request.question,
                spread_name=spread["spread_name"],
                position_label=pos["label"],
                position_meaning=pos["meaning"],
                card_name_cn=card["name_cn"],
                card_name_en=card["name_en"],
                orientation=card["orientation"],
                keywords=meaning["keywords"],
                core_meaning=meaning["core_meaning"],
                advice=meaning.get("advice", ""),
                reflection_prompt=meaning.get("reflection_prompt", ""),
            )

            interpretation = CardInterpretation(
                position_index=pos["position_index"],
                position_label=pos["label"],
                card_id=card["id"],
                card_code=card["card_code"],
                card_name_cn=card["name_cn"],
                card_name_en=card["name_en"],
                orientation=card["orientation"],
                keywords=llm_json["keywords"],
                base_meaning=meaning["core_meaning"],
                position_interpretation=llm_json["position_interpretation"],
                reflection_question=llm_json["reflection_question"],
                caution_note=llm_json["caution_note"],
            )

            results.append(interpretation)

        self.repository.mark_tarot_session_completed(session_row_id)

        return DrawInterpretResult(
            session_id=session_id,
            draw_id=draw_id,
            spread_code=spread["spread_code"],
            spread_name=spread["spread_name"],
            cards=results,
            trace=DrawInterpretTrace(
                seed=seed,
                deck_type=self.DECK_TYPE,
                prompt_name=self.PROMPT_NAME,
                prompt_version=self.PROMPT_VERSION,
                model_name="unknown",
            ),
        )