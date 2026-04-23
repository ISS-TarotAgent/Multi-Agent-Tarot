from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.domain.enums import SpreadType, WorkflowStatus
from app.domain.repositories.tarot_reading_repository import ReadingAggregate
from app.schemas.persistence import ReadingRecord, SessionMessageRecord, SessionRecord
from app.schemas.workflow import TraceEventPayload
from app.schemas.workflow.tarot_workflow_state import TarotWorkflowState


@dataclass(slots=True)
class SessionAggregate:
    session: SessionRecord
    messages: list[SessionMessageRecord]
    reading: ReadingRecord | None


class TarotSessionRepository(Protocol):
    def create_session(
        self,
        *,
        session_id: str,
        locale: str,
        spread_type: SpreadType,
        metadata: dict[str, Any] | None,
        created_at: datetime,
    ) -> SessionRecord: ...

    def get_session(self, session_id: str) -> SessionAggregate | None: ...

    def save_question_evaluation(
        self,
        *,
        session_id: str,
        raw_question: str,
        normalized_question: str | None,
        status: WorkflowStatus,
        clarifier_question: str | None,
        trace_events: list[TraceEventPayload],
        updated_at: datetime,
    ) -> SessionAggregate: ...

    def save_clarification_evaluation(
        self,
        *,
        session_id: str,
        answer_text: str,
        normalized_question: str | None,
        status: WorkflowStatus,
        next_clarifier_question: str | None,
        trace_events: list[TraceEventPayload],
        updated_at: datetime,
    ) -> SessionAggregate: ...

    def start_session_reading(
        self,
        *,
        session_id: str,
        reading_id: str,
        created_at: datetime,
    ) -> None: ...

    def save_session_workflow_result(self, state: TarotWorkflowState) -> None: ...

    def get_reading(self, reading_id: str) -> ReadingAggregate | None: ...
