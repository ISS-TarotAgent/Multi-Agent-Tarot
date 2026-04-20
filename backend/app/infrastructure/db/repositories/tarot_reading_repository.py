from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import (
    RiskLevel,
    SenderRole,
    SessionMessageType,
    SpreadType,
    TraceEventStatus,
    WorkflowStatus,
)
from app.domain.repositories import ReadingAggregate, SessionAggregate
from app.infrastructure.db.models import (
    ReadingCardModel,
    ReadingModel,
    SafetyReviewModel,
    SessionMessageModel,
    SessionModel,
    TraceEventModel,
)
from app.schemas.persistence import (
    ReadingCardRecord,
    ReadingRecord,
    SafetyReviewRecord,
    SessionMessageRecord,
    SessionRecord,
    TraceEventRecord,
)
from app.schemas.workflow import TarotWorkflowState, TraceEventPayload


class SqlAlchemyTarotReadingRepository:
    """Persists and retrieves reading and session aggregates from SQLAlchemy models."""

    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session

    def create_session(
        self,
        *,
        session_id: str,
        locale: str,
        spread_type: SpreadType,
        metadata: dict[str, object] | None,
        created_at: datetime,
    ) -> SessionRecord:
        session_model = SessionModel(
            id=session_id,
            status=WorkflowStatus.CREATED.value,
            locale=locale,
            spread_type=spread_type.value,
            normalized_question=None,
            created_at=created_at,
            updated_at=created_at,
            completed_at=None,
        )
        self._db_session.add(session_model)
        self._db_session.add(
            TraceEventModel(
                id=self._new_id(),
                session_id=session_id,
                reading_id=None,
                step_name="session_bootstrap",
                event_status=TraceEventStatus.SUCCEEDED.value,
                attempt_no=1,
                latency_ms=None,
                error_code=None,
                trace_payload={
                    "locale": locale,
                    "spread_type": spread_type.value,
                    "metadata": metadata,
                },
                created_at=created_at,
            )
        )
        self._db_session.commit()
        self._db_session.refresh(session_model)
        return SessionRecord.model_validate(session_model)

    def get_session(self, session_id: str) -> SessionAggregate | None:
        session_model = self._db_session.scalar(
            select(SessionModel)
            .where(SessionModel.id == session_id)
            .options(
                selectinload(SessionModel.messages),
                selectinload(SessionModel.reading),
            )
        )
        if session_model is None:
            return None

        return SessionAggregate(
            session=SessionRecord.model_validate(session_model),
            messages=[
                SessionMessageRecord.model_validate(message)
                for message in sorted(session_model.messages, key=lambda item: (item.turn_index, item.created_at))
            ],
            reading=(
                ReadingRecord.model_validate(session_model.reading)
                if session_model.reading is not None
                else None
            ),
        )

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
    ) -> SessionAggregate:
        session_model = self._db_session.get(SessionModel, session_id)
        if session_model is None:
            raise ValueError("session record was not found.")

        session_model.status = status.value
        session_model.normalized_question = normalized_question
        session_model.updated_at = updated_at

        self._db_session.add(
            SessionMessageModel(
                id=self._new_id(),
                session_id=session_id,
                message_type=SessionMessageType.ORIGINAL_QUESTION.value,
                sender_role=SenderRole.USER.value,
                turn_index=1,
                content=raw_question,
                created_at=updated_at,
            )
        )
        if clarifier_question is not None:
            self._db_session.add(
                SessionMessageModel(
                    id=self._new_id(),
                    session_id=session_id,
                    message_type=SessionMessageType.CLARIFIER_QUESTION.value,
                    sender_role=SenderRole.AGENT.value,
                    turn_index=2,
                    content=clarifier_question,
                    created_at=updated_at,
                )
            )

        self._add_trace_events(trace_events, session_id=session_id, reading_id=None)
        self._add_persistence_trace(
            session_id=session_id,
            reading_id=None,
            status=status,
            created_at=updated_at,
        )
        self._db_session.commit()
        self._db_session.expire_all()
        aggregate = self.get_session(session_id)
        if aggregate is None:
            raise ValueError("session aggregate was not found after question evaluation.")
        return aggregate

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
    ) -> SessionAggregate:
        session_model = self._db_session.scalar(
            select(SessionModel)
            .where(SessionModel.id == session_id)
            .options(selectinload(SessionModel.messages))
        )
        if session_model is None:
            raise ValueError("session record was not found.")

        next_turn_index = self._next_turn_index(session_model.messages)
        session_model.status = status.value
        session_model.normalized_question = normalized_question
        session_model.updated_at = updated_at

        self._db_session.add(
            SessionMessageModel(
                id=self._new_id(),
                session_id=session_id,
                message_type=SessionMessageType.CLARIFICATION_ANSWER.value,
                sender_role=SenderRole.USER.value,
                turn_index=next_turn_index,
                content=answer_text,
                created_at=updated_at,
            )
        )
        if next_clarifier_question is not None:
            self._db_session.add(
                SessionMessageModel(
                    id=self._new_id(),
                    session_id=session_id,
                    message_type=SessionMessageType.CLARIFIER_QUESTION.value,
                    sender_role=SenderRole.AGENT.value,
                    turn_index=next_turn_index + 1,
                    content=next_clarifier_question,
                    created_at=updated_at,
                )
            )

        self._add_trace_events(trace_events, session_id=session_id, reading_id=None)
        self._add_persistence_trace(
            session_id=session_id,
            reading_id=None,
            status=status,
            created_at=updated_at,
        )
        self._db_session.commit()
        self._db_session.expire_all()
        aggregate = self.get_session(session_id)
        if aggregate is None:
            raise ValueError("session aggregate was not found after clarification evaluation.")
        return aggregate

    def bootstrap_reading(
        self,
        *,
        session_id: str,
        reading_id: str,
        raw_question: str,
        locale: str,
        spread_type: SpreadType,
        created_at: datetime,
    ) -> None:
        session_model = SessionModel(
            id=session_id,
            status=WorkflowStatus.QUESTION_RECEIVED.value,
            locale=locale,
            spread_type=spread_type.value,
            normalized_question=None,
            created_at=created_at,
            updated_at=created_at,
            completed_at=None,
        )
        original_question = SessionMessageModel(
            id=self._new_id(),
            session_id=session_id,
            message_type=SessionMessageType.ORIGINAL_QUESTION.value,
            sender_role=SenderRole.USER.value,
            turn_index=1,
            content=raw_question,
            created_at=created_at,
        )
        reading_model = ReadingModel(
            id=reading_id,
            session_id=session_id,
            status=WorkflowStatus.QUESTION_RECEIVED.value,
            normalized_question=None,
            summary=None,
            action_advice=None,
            reflection_question=None,
            risk_level=RiskLevel.LOW.value,
            fallback_used=False,
            created_at=created_at,
            completed_at=None,
        )
        self._db_session.add_all([session_model, original_question, reading_model])
        self._db_session.flush()

    def start_session_reading(
        self,
        *,
        session_id: str,
        reading_id: str,
        created_at: datetime,
    ) -> None:
        session_model = self._db_session.get(SessionModel, session_id)
        if session_model is None:
            raise ValueError("session record was not found.")

        reading_model = ReadingModel(
            id=reading_id,
            session_id=session_id,
            status=WorkflowStatus.READY_FOR_DRAW.value,
            normalized_question=session_model.normalized_question,
            summary=None,
            action_advice=None,
            reflection_question=None,
            risk_level=RiskLevel.LOW.value,
            fallback_used=False,
            created_at=created_at,
            completed_at=None,
        )
        self._db_session.add(reading_model)
        self._db_session.flush()

    def save_workflow_result(self, state: TarotWorkflowState) -> None:
        session_model = self._db_session.get(SessionModel, state.session_id)
        reading_model = self._db_session.get(ReadingModel, state.reading_id)
        if session_model is None or reading_model is None:
            raise ValueError("session or reading bootstrap record was not found.")

        completed_at = state.completed_at or datetime.now(UTC)
        session_model.status = state.status.value
        session_model.normalized_question = state.normalized_question
        session_model.updated_at = completed_at
        session_model.completed_at = completed_at if state.status in self._terminal_statuses() else None

        self._update_reading_model(reading_model=reading_model, state=state, completed_at=completed_at)

        if state.clarification_output and state.clarification_output.clarification_required:
            self._upsert_session_message(
                session_id=state.session_id,
                message_type=SessionMessageType.CLARIFIER_QUESTION,
                sender_role=SenderRole.AGENT,
                turn_index=2,
                content=state.clarification_output.clarifier_question or "",
                created_at=completed_at,
            )

        self._upsert_session_message(
            session_id=state.session_id,
            message_type=SessionMessageType.FINAL_RESULT_SUMMARY,
            sender_role=SenderRole.SYSTEM,
            turn_index=3,
            content=self._compose_final_summary(
                summary=reading_model.summary,
                action_advice=reading_model.action_advice,
                reflection_question=reading_model.reflection_question,
            ),
            created_at=completed_at,
        )

        self._replace_safety_review(reading_model=reading_model, state=state, completed_at=completed_at)
        self._add_trace_events(state.trace_events, session_id=state.session_id, reading_id=state.reading_id)
        self._add_persistence_trace(
            session_id=state.session_id,
            reading_id=state.reading_id,
            status=state.status,
            created_at=completed_at,
        )

        self._db_session.commit()
        self._db_session.expire_all()

    def save_session_workflow_result(self, state: TarotWorkflowState) -> None:
        session_model = self._db_session.scalar(
            select(SessionModel)
            .where(SessionModel.id == state.session_id)
            .options(selectinload(SessionModel.messages))
        )
        reading_model = self._db_session.get(ReadingModel, state.reading_id)
        if session_model is None or reading_model is None:
            raise ValueError("session or reading record was not found.")

        completed_at = state.completed_at or datetime.now(UTC)
        session_model.status = state.status.value
        session_model.normalized_question = state.normalized_question
        session_model.updated_at = completed_at
        session_model.completed_at = completed_at if state.status in self._terminal_statuses() else None

        self._update_reading_model(reading_model=reading_model, state=state, completed_at=completed_at)
        self._replace_safety_review(reading_model=reading_model, state=state, completed_at=completed_at)
        self._add_trace_events(state.trace_events, session_id=state.session_id, reading_id=state.reading_id)
        self._add_persistence_trace(
            session_id=state.session_id,
            reading_id=state.reading_id,
            status=state.status,
            created_at=completed_at,
        )
        self._db_session.add(
            SessionMessageModel(
                id=self._new_id(),
                session_id=state.session_id,
                message_type=SessionMessageType.FINAL_RESULT_SUMMARY.value,
                sender_role=SenderRole.SYSTEM.value,
                turn_index=self._next_turn_index(session_model.messages),
                content=self._compose_final_summary(
                    summary=reading_model.summary,
                    action_advice=reading_model.action_advice,
                    reflection_question=reading_model.reflection_question,
                ),
                created_at=completed_at,
            )
        )

        self._db_session.commit()
        self._db_session.expire_all()

    def get_reading(self, reading_id: str) -> ReadingAggregate | None:
        return self._build_reading_aggregate(
            self._db_session.scalar(
                select(ReadingModel)
                .where(ReadingModel.id == reading_id)
                .options(*self._reading_aggregate_options())
            )
        )

    def _build_reading_aggregate(self, reading_model: ReadingModel | None) -> ReadingAggregate | None:
        if reading_model is None or reading_model.session is None:
            return None

        original_question_message = self._find_message(
            reading_model.session.messages,
            SessionMessageType.ORIGINAL_QUESTION.value,
        )
        if original_question_message is None:
            raise ValueError("original question message is required for a reading aggregate.")

        clarification_message = self._find_message(
            reading_model.session.messages,
            SessionMessageType.CLARIFIER_QUESTION.value,
        )

        return ReadingAggregate(
            session=SessionRecord.model_validate(reading_model.session),
            reading=ReadingRecord.model_validate(reading_model),
            cards=[ReadingCardRecord.model_validate(card) for card in reading_model.cards],
            safety_review=(
                SafetyReviewRecord.model_validate(reading_model.safety_review)
                if reading_model.safety_review is not None
                else None
            ),
            trace_events=[
                TraceEventRecord.model_validate(event)
                for event in sorted(reading_model.trace_events, key=lambda item: item.created_at)
            ],
            original_question_message=SessionMessageRecord.model_validate(original_question_message),
            clarification_message=(
                SessionMessageRecord.model_validate(clarification_message)
                if clarification_message is not None
                else None
            ),
        )

    @staticmethod
    def _reading_aggregate_options():
        return (
            selectinload(ReadingModel.cards),
            selectinload(ReadingModel.safety_review),
            selectinload(ReadingModel.trace_events),
            selectinload(ReadingModel.session).selectinload(SessionModel.messages),
        )

    @staticmethod
    def _find_message(messages: list[SessionMessageModel], message_type: str) -> SessionMessageModel | None:
        for message in messages:
            if message.message_type == message_type:
                return message
        return None

    def _upsert_session_message(
        self,
        *,
        session_id: str,
        message_type: SessionMessageType,
        sender_role: SenderRole,
        turn_index: int,
        content: str,
        created_at: datetime,
    ) -> None:
        existing_message = self._db_session.scalar(
            select(SessionMessageModel).where(
                SessionMessageModel.session_id == session_id,
                SessionMessageModel.message_type == message_type.value,
            )
        )
        if existing_message is None:
            self._db_session.add(
                SessionMessageModel(
                    id=self._new_id(),
                    session_id=session_id,
                    message_type=message_type.value,
                    sender_role=sender_role.value,
                    turn_index=turn_index,
                    content=content,
                    created_at=created_at,
                )
            )
            return

        existing_message.content = content
        existing_message.turn_index = turn_index

    def _update_reading_model(
        self,
        *,
        reading_model: ReadingModel,
        state: TarotWorkflowState,
        completed_at: datetime,
    ) -> None:
        reading_model.status = state.status.value
        reading_model.normalized_question = state.normalized_question
        reading_model.summary = state.safety_output.safe_summary if state.safety_output else None
        reading_model.action_advice = state.safety_output.safe_action_advice if state.safety_output else None
        reading_model.reflection_question = (
            state.safety_output.safe_reflection_question if state.safety_output else None
        )
        reading_model.risk_level = state.safety_output.risk_level.value if state.safety_output else RiskLevel.LOW.value
        reading_model.fallback_used = state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED
        reading_model.completed_at = completed_at

        reading_model.cards.clear()
        for index, card in enumerate(state.cards, start=1):
            reading_model.cards.append(
                ReadingCardModel(
                    id=self._new_id(),
                    reading_id=state.reading_id,
                    position=card.position.value,
                    sort_order=index,
                    card_code=card.card_code,
                    card_name=card.card_name,
                    orientation=card.orientation.value,
                    interpretation=card.interpretation,
                    created_at=completed_at,
                )
            )

    def _replace_safety_review(
        self,
        *,
        reading_model: ReadingModel,
        state: TarotWorkflowState,
        completed_at: datetime,
    ) -> None:
        if reading_model.safety_review is not None:
            self._db_session.delete(reading_model.safety_review)
            self._db_session.flush()

        if state.safety_output is None:
            return

        reading_model.safety_review = SafetyReviewModel(
            id=self._new_id(),
            reading_id=state.reading_id,
            risk_level=state.safety_output.risk_level.value,
            action_taken=state.safety_output.action_taken.value,
            review_notes=state.safety_output.review_notes,
            safe_output=self._compose_final_summary(
                summary=state.safety_output.safe_summary,
                action_advice=state.safety_output.safe_action_advice,
                reflection_question=state.safety_output.safe_reflection_question,
            ),
            created_at=completed_at,
        )

    def _add_trace_events(
        self,
        trace_events: list[TraceEventPayload],
        *,
        session_id: str,
        reading_id: str | None,
    ) -> None:
        for trace_event in trace_events:
            self._db_session.add(
                TraceEventModel(
                    id=trace_event.event_id,
                    session_id=session_id,
                    reading_id=reading_id,
                    step_name=trace_event.step_name,
                    event_status=trace_event.event_status.value,
                    attempt_no=trace_event.attempt_no,
                    latency_ms=trace_event.latency_ms,
                    error_code=trace_event.error_code,
                    trace_payload=trace_event.payload,
                    created_at=trace_event.created_at,
                )
            )

    def _add_persistence_trace(
        self,
        *,
        session_id: str,
        reading_id: str | None,
        status: WorkflowStatus,
        created_at: datetime,
    ) -> None:
        self._db_session.add(
            TraceEventModel(
                id=self._new_id(),
                session_id=session_id,
                reading_id=reading_id,
                step_name="persistence",
                event_status=TraceEventStatus.SUCCEEDED.value,
                attempt_no=1,
                latency_ms=None,
                error_code=None,
                trace_payload={"status": status.value},
                created_at=created_at,
            )
        )

    @staticmethod
    def _compose_final_summary(
        *,
        summary: str | None,
        action_advice: str | None,
        reflection_question: str | None,
    ) -> str:
        parts = [item for item in [summary, action_advice, reflection_question] if item]
        return "\n".join(parts)

    @staticmethod
    def _terminal_statuses() -> set[WorkflowStatus]:
        return {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.SAFE_FALLBACK_RETURNED,
            WorkflowStatus.FAILED,
        }

    @staticmethod
    def _next_turn_index(messages: list[SessionMessageModel]) -> int:
        if not messages:
            return 1
        return max(message.turn_index for message in messages) + 1

    @staticmethod
    def _new_id() -> str:
        from uuid import uuid4

        return str(uuid4())
