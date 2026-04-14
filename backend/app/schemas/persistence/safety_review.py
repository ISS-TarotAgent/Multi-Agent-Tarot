from __future__ import annotations

from datetime import datetime

from app.domain.enums import RiskLevel, SafetyAction
from app.schemas.persistence.common import PersistenceSchema


class SafetyReviewRecord(PersistenceSchema):
    id: str
    reading_id: str
    risk_level: RiskLevel
    action_taken: SafetyAction
    review_notes: str | None = None
    safe_output: str | None = None
    created_at: datetime
