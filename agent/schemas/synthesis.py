from __future__ import annotations

from pydantic import field_validator

from agent.schemas.common import AgentSchema
from agent.schemas.draw import DrawCard


class SynthesisInput(AgentSchema):
    normalized_question: str
    cards: list[DrawCard]

    @field_validator("normalized_question")
    @classmethod
    def validate_normalized_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("normalized_question must not be empty.")
        return normalized


class SynthesisOutput(AgentSchema):
    summary: str
    action_advice: str
    reflection_question: str

    @field_validator("summary", "action_advice", "reflection_question")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("synthesis fields must not be empty.")
        return normalized
