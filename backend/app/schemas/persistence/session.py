from __future__ import annotations

from datetime import datetime

from app.domain.enums import SenderRole, SessionMessageType, SpreadType, WorkflowStatus
from app.schemas.persistence.common import PersistenceSchema


class SessionRecord(PersistenceSchema):
    id: str
    status: WorkflowStatus
    locale: str
    spread_type: SpreadType
    normalized_question: str | None = None
    intent_tag: str | None = None
    clarification_prompts: list = []
    clarification_answers: dict = {}
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class SessionMessageRecord(PersistenceSchema):
    id: str
    session_id: str
    message_type: SessionMessageType
    sender_role: SenderRole
    turn_index: int
    content: str
    created_at: datetime
