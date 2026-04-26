"""Tests for locale propagation into LLM-backed agent prompts."""

from __future__ import annotations

import json
from typing import Any

from agent.core.llm_agents import LLMClarifierAgent, LLMDrawAgent
from agent.core.model_gateway import ModelResponse
from agent.schemas.clarifier import ClarifierFinalizeInput, ClarifierInput
from agent.schemas.draw import DrawInput
from backend.app.domain.enums import SpreadType


class CapturingGateway:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        self.calls.append(
            {
                "user_prompt": user_prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "kwargs": kwargs,
            }
        )
        response = self.responses.pop(0)
        return ModelResponse(content=json.dumps(response), model="test")


def test_clarifier_init_prompt_includes_locale() -> None:
    gateway = CapturingGateway(
        [
            {
                "normalized_question": "Should I change jobs this year?",
                "intent_tag": "career",
                "clarification_prompts": [
                    {
                        "id": "q1",
                        "question": "What decision are you weighing most closely?",
                        "helper_text": "This gives the reading a concrete focus.",
                        "placeholder": "For example: whether to accept a new offer.",
                    }
                ],
            }
        ]
    )

    LLMClarifierAgent(gateway).run(
        ClarifierInput(raw_question="Should I change jobs this year?", locale="en")
    )

    assert 'locale: "en"' in gateway.calls[0]["user_prompt"]


def test_clarifier_finalize_prompt_includes_locale() -> None:
    gateway = CapturingGateway(
        [
            {
                "reframed_question": "How can I understand the career decision in front of me?",
                "topic": "Career decision",
                "time_horizon": "This year",
                "intent": "Understand the inner direction behind a job decision.",
                "constraints": [],
            }
        ]
    )

    LLMClarifierAgent(gateway).finalize(
        ClarifierFinalizeInput(
            normalized_question="Should I change jobs this year?",
            intent_tag="career",
            locale="en",
            clarification_answers={"q1": "A new offer versus my current role."},
        )
    )

    assert '"locale": "en"' in gateway.calls[0]["user_prompt"]


def test_draw_prompt_payload_includes_locale() -> None:
    gateway = CapturingGateway(
        [
            {
                "interpretation": "This card points to the conditions shaping the question.",
                "reflection_question": "What pattern is asking for attention?",
                "caution_note": "Avoid treating the card as a fixed prediction.",
                "keywords": ["context", "pattern", "choice"],
            },
            {
                "interpretation": "This card describes the current tension.",
                "reflection_question": "What feels unresolved right now?",
                "caution_note": "Do not rush the decision.",
                "keywords": ["tension", "attention", "timing"],
            },
            {
                "interpretation": "This card suggests a practical next step.",
                "reflection_question": "What action can you take with clarity?",
                "caution_note": "Keep the step grounded.",
                "keywords": ["action", "clarity", "grounding"],
            },
        ]
    )

    LLMDrawAgent(gateway).run(
        DrawInput(
            question="Should I change jobs this year?",
            locale="en",
            spread_type=SpreadType.THREE_CARD_REFLECTION,
        )
    )

    first_payload = json.loads(gateway.calls[0]["user_prompt"])
    assert first_payload["locale"] == "en"
    assert "locale" in (gateway.calls[0]["system_prompt"] or "")
