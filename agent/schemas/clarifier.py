from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from agent.schemas.common import AgentSchema


class ClarifierInput(AgentSchema):
    raw_question: str
    locale: str = "zh-CN"

    @field_validator("raw_question")
    @classmethod
    def validate_raw_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("raw_question must not be empty.")
        return normalized


class ClarifierOutput(AgentSchema):
    normalized_question: str
    clarification_required: bool
    clarifier_question: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_question_pair(self) -> "ClarifierOutput":
        if self.clarification_required and not self.clarifier_question:
            raise ValueError("clarifier_question is required when clarification_required is true.")
        if not self.clarification_required and self.clarifier_question is not None:
            raise ValueError("clarifier_question must be null when clarification_required is false.")
        return self
