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


class LLMSafetyCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    synthesis_text: str
    question: str
    keyword_hits: list[str]


class LLMSafetyCheckOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_level: str  # "HIGH" | "MEDIUM" | "LOW"
    reasoning: str


class LLMInputSecurityCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    locale: str = "zh-CN"


class LLMInputSecurityCheckOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str  # "continue" | "rewrite" | "block"
    risk_type: str  # "safe" | threat category string
    risk_level: str  # "LOW" | "MEDIUM" | "HIGH"
    sanitized_content: str | None
    reasoning: str
