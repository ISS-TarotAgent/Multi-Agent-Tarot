"""LLM-backed agent implementations for Clarifier, Draw, and Synthesis nodes."""

from __future__ import annotations

import json

from agent.core.model_gateway import ModelGateway
from agent.core.prompt_registry import load_prompt
from agent.schemas.clarifier import ClarifierInput, ClarifierOutput
from agent.schemas.draw import DrawCard, DrawInput, DrawOutput
from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from backend.app.domain.enums import CardOrientation, CardPosition


class LLMClarifierAgent:
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        self._system_prompt = load_prompt("clarifier_system_prompt")

    def run(self, payload: ClarifierInput) -> ClarifierOutput:
        user_prompt = f"locale: {payload.locale}\nquestion: {payload.raw_question}"
        response = self._gateway.run(
            user_prompt,
            system_prompt=self._system_prompt,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.content)
        return ClarifierOutput(
            normalized_question=data["normalized_question"],
            clarification_required=bool(data["clarification_required"]),
            clarifier_question=data.get("clarifier_question"),
        )


class LLMDrawAgent:
    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        self._system_prompt = load_prompt("draw_interpret_system_prompt")

    def run(self, payload: DrawInput) -> DrawOutput:
        user_prompt = (
            f"locale: {payload.locale}\n"
            f"spread_type: {payload.spread_type.value}\n"
            f"question: {payload.question}"
        )
        response = self._gateway.run(
            user_prompt,
            system_prompt=self._system_prompt,
            temperature=1.0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.content)
        cards = [
            DrawCard(
                position=CardPosition(c["position"]),
                card_code=c["card_code"],
                card_name=c["card_name"],
                orientation=CardOrientation(c["orientation"]),
                interpretation=c["interpretation"],
            )
            for c in data["cards"]
        ]
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
        response = self._gateway.run(
            user_prompt,
            system_prompt=self._system_prompt,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.content)
        return SynthesisOutput(
            summary=data["summary"],
            action_advice=data["action_advice"],
            reflection_question=data["reflection_question"],
        )
