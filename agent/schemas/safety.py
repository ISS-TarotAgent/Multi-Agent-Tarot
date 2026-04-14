from __future__ import annotations

from pydantic import field_validator

from agent.schemas.common import AgentSchema
from app.domain.enums import RiskLevel, SafetyAction


class SafetyReviewInput(AgentSchema):
    summary: str
    action_advice: str
    reflection_question: str
    normalized_question: str

    @field_validator("summary", "action_advice", "reflection_question", "normalized_question")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("safety input fields must not be empty.")
        return normalized


class SafetyReviewOutput(AgentSchema):
    risk_level: RiskLevel
    action_taken: SafetyAction
    safe_summary: str
    safe_action_advice: str
    safe_reflection_question: str
    review_notes: str | None = None

    @field_validator("safe_summary", "safe_action_advice", "safe_reflection_question")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("safety output fields must not be empty.")
        return normalized
