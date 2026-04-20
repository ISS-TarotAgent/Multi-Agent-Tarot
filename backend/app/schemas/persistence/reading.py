from __future__ import annotations

from datetime import datetime

from app.domain.enums import CardOrientation, CardPosition, RiskLevel, WorkflowStatus
from app.schemas.persistence.common import PersistenceSchema


class ReadingRecord(PersistenceSchema):
    id: str
    session_id: str
    status: WorkflowStatus
    normalized_question: str | None = None
    summary: str | None = None
    action_advice: str | None = None
    reflection_question: str | None = None
    risk_level: RiskLevel
    fallback_used: bool
    created_at: datetime
    completed_at: datetime | None = None


class ReadingCardRecord(PersistenceSchema):
    id: str
    reading_id: str
    position: CardPosition
    sort_order: int
    card_code: str
    card_name: str
    orientation: CardOrientation
    interpretation: str
    created_at: datetime
