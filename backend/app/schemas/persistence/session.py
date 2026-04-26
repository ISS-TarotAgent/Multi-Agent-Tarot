from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.domain.enums import SenderRole, SessionMessageType, SpreadType, WorkflowStatus
from app.schemas.persistence.common import PersistenceSchema


class SessionRecord(PersistenceSchema):
    id: str
    status: WorkflowStatus
    locale: str
    spread_type: SpreadType
    normalized_question: str | None = None
    intent_tag: str | None = None
    clarification_prompts: list = Field(default_factory=list)
    clarification_answers: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @field_validator("clarification_prompts", mode="before")
    @classmethod
    def default_clarification_prompts(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("clarification_answers", mode="before")
    @classmethod
    def default_clarification_answers(cls, value: object) -> object:
        return {} if value is None else value


class SessionMessageRecord(PersistenceSchema):
    id: str
    session_id: str
    message_type: SessionMessageType
    sender_role: SenderRole
    turn_index: int
    content: str
    created_at: datetime
