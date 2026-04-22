from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.domain.enums import CardOrientation, CardPosition, RiskLevel, SafetyAction, SpreadType, WorkflowStatus
from app.schemas.api.common import ApiSchema


class CreateReadingRequest(ApiSchema):
    question: str
    locale: str = "zh-CN"
    spread_type: SpreadType = SpreadType.THREE_CARD_REFLECTION
    client_request_id: str | None = None
    metadata: dict[str, Any] | None = None
    # When True, the clarifier will finalize immediately without asking for more context.
    # Frontend sets this after MAX_CLARIFICATION_TURNS is reached.
    skip_clarification: bool = False

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty.")
        if len(normalized) > 2000:
            raise ValueError("question must not exceed 2000 characters.")
        return normalized


class ReadingQuestionPayload(ApiSchema):
    raw_question: str
    normalized_question: str | None = None


class ReadingClarificationPayload(ApiSchema):
    required: bool
    question_text: str | None = None
    answer_text: str | None = None


class ReadingCardPayload(ApiSchema):
    position: CardPosition
    card_code: str
    card_name: str
    orientation: CardOrientation
    interpretation: str
    reflection_question: str | None = None
    caution_note: str | None = None
    keywords: list[str] = []


class ReadingSynthesisPayload(ApiSchema):
    summary: str | None = None
    action_advice: str | None = None
    reflection_question: str | None = None


class ReadingSafetyPayload(ApiSchema):
    risk_level: RiskLevel
    action_taken: SafetyAction
    review_notes: str | None = None


class ReadingTraceSummaryPayload(ApiSchema):
    event_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    error_count: int = Field(ge=0)


class ReadingResultResponse(ApiSchema):
    reading_id: str
    session_id: str
    status: WorkflowStatus
    locale: str
    spread_type: SpreadType
    question: ReadingQuestionPayload
    clarification: ReadingClarificationPayload
    cards: list[ReadingCardPayload]
    synthesis: ReadingSynthesisPayload
    safety: ReadingSafetyPayload
    trace_summary: ReadingTraceSummaryPayload
    created_at: datetime
    completed_at: datetime | None = None
