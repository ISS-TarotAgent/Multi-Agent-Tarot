from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.domain.enums import RiskLevel, SafetyAction


class SafetyReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    action_advice: str
    reflection_question: str
    locale: str


class SafetyReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_level: RiskLevel
    action_taken: SafetyAction
    review_notes: str | None = None
    safe_summary: str
    safe_action_advice: str
    safe_reflection_question: str
