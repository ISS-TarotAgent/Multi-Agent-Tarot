from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.domain.enums import SenderRole, SessionMessageType, SpreadType, WorkflowStatus
from app.schemas.api.common import ApiSchema


class CreateSessionRequest(ApiSchema):
    locale: str = "zh-CN"
    spread_type: SpreadType = SpreadType.THREE_CARD_REFLECTION
    metadata: dict[str, Any] | None = None


class CreateSessionResponse(ApiSchema):
    session_id: str
    status: WorkflowStatus
    locale: str
    spread_type: SpreadType
    created_at: datetime


class SubmitQuestionRequest(ApiSchema):
    raw_question: str
    skip_clarification: bool = False

    @field_validator("raw_question")
    @classmethod
    def validate_raw_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("raw_question must not be empty.")
        if len(normalized) > 2000:
            raise ValueError("raw_question must not exceed 2000 characters.")
        return normalized


class SubmitQuestionResponse(ApiSchema):
    session_id: str
    status: WorkflowStatus
    normalized_question: str | None = None
    clarification_required: bool
    clarifier_question: str | None = None
    updated_at: datetime


class SubmitClarificationRequest(ApiSchema):
    answer_text: str
    turn_index: int = Field(ge=1)

    @field_validator("answer_text")
    @classmethod
    def validate_answer_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("answer_text must not be empty.")
        if len(normalized) > 2000:
            raise ValueError("answer_text must not exceed 2000 characters.")
        return normalized


class SubmitClarificationResponse(ApiSchema):
    session_id: str
    status: WorkflowStatus
    normalized_question: str | None = None
    clarification_required: bool
    next_clarifier_question: str | None = None
    updated_at: datetime


class RunSessionRequest(ApiSchema):
    pass


class SessionSnapshotResponse(ApiSchema):
    session_id: str
    status: WorkflowStatus
    locale: str
    spread_type: SpreadType
    normalized_question: str | None = None
    current_reading_id: str | None = None
    clarification_turn_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class SessionHistoryItemResponse(ApiSchema):
    message_id: str
    message_type: SessionMessageType
    sender_role: SenderRole
    turn_index: int = Field(ge=1)
    content: str
    created_at: datetime


class SessionHistoryResponse(ApiSchema):
    session_id: str
    items: list[SessionHistoryItemResponse]
