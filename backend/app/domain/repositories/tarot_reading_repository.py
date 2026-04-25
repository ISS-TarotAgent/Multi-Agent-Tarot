from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.enums import SpreadType
from app.schemas.persistence import (
    ReadingCardRecord,
    ReadingRecord,
    SafetyReviewRecord,
    SessionMessageRecord,
    SessionRecord,
    TraceEventRecord,
)
from app.schemas.workflow import TarotWorkflowState


@dataclass(slots=True)
class ReadingAggregate:
    session: SessionRecord
    reading: ReadingRecord
    cards: list[ReadingCardRecord]
    safety_review: SafetyReviewRecord | None
    trace_events: list[TraceEventRecord]
    original_question_message: SessionMessageRecord
    clarification_message: SessionMessageRecord | None


class TarotReadingRepository(Protocol):
    def bootstrap_reading(
        self,
        *,
        session_id: str,
        reading_id: str,
        raw_question: str,
        locale: str,
        spread_type: SpreadType,
        created_at: datetime,
    ) -> None: ...

    def save_workflow_result(self, state: TarotWorkflowState) -> None: ...

    def get_reading(self, reading_id: str) -> ReadingAggregate | None: ...
