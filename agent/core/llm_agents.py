"""LLM-backed agent implementations for Clarifier, Draw, and Synthesis nodes."""

from __future__ import annotations

import json
import re

from agent.core.model_gateway import ModelGateway
from agent.core.prompt_registry import load_prompt
from agent.schemas.clarifier import (
    ClarificationPrompt,
    ClarifierFinalizeInput,
    ClarifierFinalizeOutput,
    ClarifierInput,
    ClarifierOutput,
)
from agent.schemas.draw import DrawCard, DrawInput, DrawOutput
from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from backend.app.domain.enums import CardOrientation, CardPosition

_MAX_RETRIES = 3
_POSITIONS = ["PAST", "PRESENT", "FUTURE"]
# 预设牌阵的位置含义，用于提示 LLM 生成针对每张牌的解读。可以根据需要调整或扩展。
_POSITION_MEANINGS = {
    "PAST":    "The background, past influences, and what has shaped the current situation.",
    "PRESENT": "The current core tension, energy, or challenge being navigated right now.",
    "FUTURE":  "The direction that can open up, and what can be worked toward from here.",
}
# 剥离可选的 markdown 代码，提取其中的 JSON 内容进行解析。适用于 LLM 输出时可能包含的 ```json ... ``` 格式。
_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _parse_json(raw: str) -> dict:
    """Strip optional markdown fences then parse JSON."""
    match = _FENCE_RE.search(raw)
    text = match.group(1) if match else raw
    return json.loads(text.strip())


class LLMClarifierAgent:
    # 初始化Agent和模型网关，加载提示模板，并在run和finalize方法中实现两阶段的澄清逻辑。
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        self._init_prompt_template = load_prompt("clarifier_init")
        self._finalize_prompt_template = load_prompt("clarifier_finalize")
    
    # run方法负责第一阶段的处理，生成澄清问题和意图标签;
    def run(self, payload: ClarifierInput) -> ClarifierOutput:
        """Phase 1: identify intent and generate clarification prompts."""
        prompt = self._init_prompt_template.replace("{raw_question}", payload.raw_question)
        last_exc: Exception | None = None
        for _ in range(_MAX_RETRIES):
            try:
                # temperature设置较低以提高输出的稳定性和可预测性，response_format指定期望的结构化JSON输出，方便后续解析和使用。
                response = self._gateway.run(
                    prompt,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    generation_name="clarifier_init",
                )
                data = _parse_json(response.content)

                intent_tag = data.get("intent_tag", "growth")
                if intent_tag not in ("career", "relationship", "study", "emotion", "growth"):
                    intent_tag = "growth"

                raw_prompts: list[dict] = data.get("clarification_prompts", [])
                clarification_prompts = [
                    ClarificationPrompt(**p) for p in raw_prompts[:3]
                ]

                return ClarifierOutput(
                    normalized_question=data.get("normalized_question") or payload.raw_question,
                    clarification_required=len(clarification_prompts) > 0,
                    clarifier_question=clarification_prompts[0].question if clarification_prompts else None,
                    intent_tag=intent_tag,
                    clarification_prompts=clarification_prompts,
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"ClarifierAgent.run failed after {_MAX_RETRIES} attempts") from last_exc
    
    # finalize方法负责第二阶段的处理，根据用户对澄清问题的回答生成重构问题和相关信息。
    def finalize(self, payload: ClarifierFinalizeInput) -> ClarifierFinalizeOutput:
        """Phase 2: synthesize clarification answers into a reframed question."""
        answers_json = json.dumps(payload.clarification_answers, ensure_ascii=False)
        prompt = (
            self._finalize_prompt_template
            .replace('"{original_question}"', json.dumps(payload.normalized_question, ensure_ascii=False))
            .replace('"{intent_tag}"', json.dumps(payload.intent_tag, ensure_ascii=False))
            .replace("{clarification_answers}", answers_json)
        )
        last_exc: Exception | None = None
        for _ in range(_MAX_RETRIES):
            try:
                response = self._gateway.run(
                    prompt,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    generation_name="clarifier_finalize",
                )
                data = _parse_json(response.content)
                return ClarifierFinalizeOutput(
                    reframed_question=data["reframed_question"],
                    topic=data.get("topic", ""),
                    time_horizon=data.get("time_horizon", "未指定"),
                    intent=data.get("intent", ""),
                    constraints=data.get("constraints", []),
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"ClarifierAgent.finalize failed after {_MAX_RETRIES} attempts") from last_exc


class LLMDrawAgent:
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        self._system_prompt = load_prompt("draw_interpret_system_prompt")

    def run(self, payload: DrawInput) -> DrawOutput:
        from agent.core.tarot_deck import draw_cards

        drawn, seed = draw_cards(3, allow_reversed=True)
        cards: list[DrawCard] = []

        for pos, c in zip(_POSITIONS, drawn):
            card_input = json.dumps({
                "question": payload.question,
                "position_label": pos,
                "position_meaning": _POSITION_MEANINGS[pos],
                "card_name": c["card_name"],
                "card_code": c["card_code"],
                "orientation": c["orientation"],
                "meaning": c["meaning"],
            }, ensure_ascii=False)

            last_exc: Exception | None = None
            for _ in range(_MAX_RETRIES):
                try:
                    response = self._gateway.run(
                        card_input,
                        system_prompt=self._system_prompt,
                        temperature=0.7,
                        response_format={"type": "json_object"},
                        generation_name=f"draw_interpret_{pos.lower()}",
                    )
                    data = _parse_json(response.content)
                    cards.append(DrawCard(
                        position=CardPosition(pos),
                        card_code=c["card_code"],
                        card_name=c["card_name"],
                        orientation=CardOrientation(c["orientation"]),
                        interpretation=data["interpretation"],
                        reflection_question=data.get("reflection_question"),
                        caution_note=data.get("caution_note"),
                        keywords=data.get("keywords", []),
                        meaning=c["meaning"],
                        seed=seed,
                    ))
                    break
                except Exception as exc:
                    last_exc = exc
            else:
                raise RuntimeError(
                    f"DrawAgent failed on {pos} card after {_MAX_RETRIES} attempts"
                ) from last_exc

        return DrawOutput(cards=cards)


class LLMSynthesisAgent:
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        self._system_prompt = load_prompt("synthesis_system_prompt")

    def run(self, payload: SynthesisInput) -> SynthesisOutput:
        interpretations_text = "\n".join(
            f"- {interp}" for interp in payload.card_interpretations
        )
        user_prompt = (
            f"locale: {payload.locale}\n"
            f"question: {payload.normalized_question}\n"
            f"card_interpretations:\n{interpretations_text}"
        )
        last_exc: Exception | None = None
        for _ in range(_MAX_RETRIES):
            try:
                response = self._gateway.run(
                    user_prompt,
                    system_prompt=self._system_prompt,
                    temperature=0.7,
                    response_format={"type": "json_object"},
                    generation_name="synthesis",
                )
                data = _parse_json(response.content)
                return SynthesisOutput(
                    summary=data["summary"],
                    action_advice=data["action_advice"],
                    reflection_question=data["reflection_question"],
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"SynthesisAgent failed after {_MAX_RETRIES} attempts") from last_exc
