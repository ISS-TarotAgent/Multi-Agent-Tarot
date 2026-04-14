from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from agent.workflows import TarotReflectionWorkflow
from app.api.errors import AppError
from app.application.services.tarot_reading_service import TarotReadingService
from app.domain.enums import SessionMessageType, WorkflowStatus
from app.domain.repositories import SessionAggregate, TarotSessionRepository
from app.infrastructure.observability import NoOpWorkflowObserver
from app.schemas.api.readings import ReadingResultResponse
from app.schemas.api.sessions import (
    CreateSessionRequest,
    CreateSessionResponse,
    SessionHistoryItemResponse,
    SessionHistoryResponse,
    SessionSnapshotResponse,
    SubmitClarificationRequest,
    SubmitClarificationResponse,
    SubmitQuestionRequest,
    SubmitQuestionResponse,
)
from app.schemas.persistence import SessionMessageRecord
from app.schemas.workflow.tarot_workflow_state import TarotWorkflowState


class TarotSessionService:
    """Coordinates the session-oriented phase-3 API surface."""

    _TERMINAL_STATUSES = {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.SAFE_FALLBACK_RETURNED,
        WorkflowStatus.FAILED,
    }

    def __init__(
        self,
        repository: TarotSessionRepository,
        workflow: TarotReflectionWorkflow | None = None,
        observer: NoOpWorkflowObserver | None = None,
    ) -> None:
        self._repository = repository
        self._observer = observer or NoOpWorkflowObserver()
        self._workflow = workflow or TarotReflectionWorkflow(observer=self._observer)

    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        created_at = self._now()
        session_id = str(uuid4())

        try:
            session = self._repository.create_session(
                session_id=session_id,
                locale=request.locale,
                spread_type=request.spread_type,
                metadata=request.metadata,
                created_at=created_at,
            )
        except SQLAlchemyError as exc:
            raise AppError.dependency_unavailable("Database operation failed.", details={"reason": str(exc)}) from exc

        return CreateSessionResponse(
            session_id=session.id,
            status=session.status,
            locale=session.locale,
            spread_type=session.spread_type,
            created_at=session.created_at,
        )

    def submit_question(self, session_id: str, request: SubmitQuestionRequest) -> SubmitQuestionResponse:
        aggregate = self._get_session_or_404(session_id)
        self._ensure_state(
            aggregate=aggregate,
            allowed_statuses={WorkflowStatus.CREATED},
            action="submit_question",
        )

        with self._observer.observe_operation(
            name="tarot.session.submit_question",
            session_id=session_id,
            reading_id=None,
            input_payload={"raw_question": request.raw_question},
            metadata={"locale": aggregate.session.locale},
        ) as operation:
            try:
                question_state = self._workflow.evaluate_question(
                    session_id=session_id,
                    reading_id=f"session-eval:{session_id}",
                    raw_question=request.raw_question,
                    locale=aggregate.session.locale,
                    spread_type=aggregate.session.spread_type,
                    trace_reading_id=None,
                    persistence_handler=lambda state: self._repository.save_question_evaluation(
                        session_id=session_id,
                        raw_question=request.raw_question,
                        normalized_question=self._require_clarification_output(state).normalized_question,
                        status=state.status,
                        clarifier_question=self._require_clarification_output(state).clarifier_question,
                        trace_events=state.trace_events,
                        updated_at=self._now(),
                    ),
                )
                updated = self._get_session_or_404(session_id)
            except SQLAlchemyError as exc:
                operation.failure(
                    error_code="DEPENDENCY_UNAVAILABLE",
                    message="Database operation failed.",
                    metadata={"reason": str(exc)},
                )
                raise AppError.dependency_unavailable("Database operation failed.", details={"reason": str(exc)}) from exc

            clarifier_output = self._require_clarification_output(question_state)
            latest_clarifier_question = self._latest_message(updated.messages, SessionMessageType.CLARIFIER_QUESTION)
            response = SubmitQuestionResponse(
                session_id=updated.session.id,
                status=updated.session.status,
                normalized_question=updated.session.normalized_question,
                clarification_required=updated.session.status is WorkflowStatus.CLARIFYING,
                clarifier_question=latest_clarifier_question.content if latest_clarifier_question else None,
                updated_at=updated.session.updated_at,
            )
            operation.success(
                output={
                    "status": response.status.value,
                    "clarification_required": response.clarification_required,
                }
            )
            return response

    def submit_clarification(
        self,
        session_id: str,
        request: SubmitClarificationRequest,
    ) -> SubmitClarificationResponse:
        aggregate = self._get_session_or_404(session_id)
        self._ensure_state(
            aggregate=aggregate,
            allowed_statuses={WorkflowStatus.CLARIFYING},
            action="submit_clarification",
        )

        expected_turn_index = self._clarification_turn_count(aggregate.messages) + 1
        if request.turn_index != expected_turn_index:
            raise AppError.invalid_state_transition(
                "Clarification turn index does not match the next expected turn.",
                details={
                    "session_id": session_id,
                    "current_status": aggregate.session.status.value,
                    "expected_turn_index": expected_turn_index,
                    "received_turn_index": request.turn_index,
                },
            )

        with self._observer.observe_operation(
            name="tarot.session.submit_clarification",
            session_id=session_id,
            reading_id=None,
            input_payload={"answer_text": request.answer_text, "turn_index": request.turn_index},
            metadata={"locale": aggregate.session.locale},
        ) as operation:
            clarifier_input = self._compose_follow_up_question(
                aggregate=aggregate,
                new_answer=request.answer_text,
            )
            try:
                question_state = self._workflow.evaluate_question(
                    session_id=session_id,
                    reading_id=f"session-eval:{session_id}",
                    raw_question=clarifier_input,
                    locale=aggregate.session.locale,
                    spread_type=aggregate.session.spread_type,
                    trace_reading_id=None,
                    persistence_handler=lambda state: self._repository.save_clarification_evaluation(
                        session_id=session_id,
                        answer_text=request.answer_text,
                        normalized_question=self._require_clarification_output(state).normalized_question,
                        status=state.status,
                        next_clarifier_question=self._require_clarification_output(state).clarifier_question,
                        trace_events=state.trace_events,
                        updated_at=self._now(),
                    ),
                )
                updated = self._get_session_or_404(session_id)
            except SQLAlchemyError as exc:
                operation.failure(
                    error_code="DEPENDENCY_UNAVAILABLE",
                    message="Database operation failed.",
                    metadata={"reason": str(exc)},
                )
                raise AppError.dependency_unavailable("Database operation failed.", details={"reason": str(exc)}) from exc

            clarifier_output = self._require_clarification_output(question_state)
            latest_clarifier_question = self._latest_message(updated.messages, SessionMessageType.CLARIFIER_QUESTION)
            response = SubmitClarificationResponse(
                session_id=updated.session.id,
                status=updated.session.status,
                normalized_question=updated.session.normalized_question,
                clarification_required=updated.session.status is WorkflowStatus.CLARIFYING,
                next_clarifier_question=(
                    latest_clarifier_question.content if updated.session.status is WorkflowStatus.CLARIFYING else None
                ),
                updated_at=updated.session.updated_at,
            )
            operation.success(
                output={
                    "status": response.status.value,
                    "clarification_required": response.clarification_required,
                }
            )
            return response

    def run_session(self, session_id: str) -> ReadingResultResponse:
        aggregate = self._get_session_or_404(session_id)
        self._ensure_state(
            aggregate=aggregate,
            allowed_statuses={WorkflowStatus.READY_FOR_DRAW},
            action="run_session",
        )

        original_question = self._required_message(aggregate.messages, SessionMessageType.ORIGINAL_QUESTION)
        reading_id = str(uuid4())
        created_at = self._now()

        with self._observer.observe_operation(
            name="tarot.session.run",
            session_id=session_id,
            reading_id=reading_id,
            input_payload={"normalized_question": aggregate.session.normalized_question},
            metadata={"locale": aggregate.session.locale},
        ) as operation:
            try:
                self._repository.start_session_reading(
                    session_id=session_id,
                    reading_id=reading_id,
                    created_at=created_at,
                )
                state = TarotWorkflowState(
                    session_id=session_id,
                    reading_id=reading_id,
                    status=WorkflowStatus.READY_FOR_DRAW,
                    locale=aggregate.session.locale,
                    spread_type=aggregate.session.spread_type,
                    raw_question=original_question.content,
                    normalized_question=aggregate.session.normalized_question or original_question.content,
                    created_at=created_at,
                )
                final_state = self._workflow.continue_from_ready_state(
                    state,
                    persistence_handler=self._repository.save_session_workflow_result,
                )
            except SQLAlchemyError as exc:
                operation.failure(
                    error_code="DEPENDENCY_UNAVAILABLE",
                    message="Database operation failed.",
                    metadata={"reason": str(exc)},
                )
                raise AppError.dependency_unavailable("Database operation failed.", details={"reason": str(exc)}) from exc

            reading_aggregate = self._repository.get_reading(reading_id)
            if reading_aggregate is None:
                operation.failure(
                    error_code="RESOURCE_NOT_FOUND",
                    message="Reading was not found after running the session.",
                    metadata={"session_id": session_id, "reading_id": reading_id},
                )
                raise AppError.resource_not_found(
                    "Reading was not found after running the session.",
                    details={"session_id": session_id, "reading_id": reading_id},
                )
            response = TarotReadingService.to_reading_response(reading_aggregate)
            operation.success(
                output={
                    "status": response.status.value,
                    "trace_event_count": response.trace_summary.event_count,
                }
            )
            return response

    def get_session_snapshot(self, session_id: str) -> SessionSnapshotResponse:
        aggregate = self._get_session_or_404(session_id)
        return SessionSnapshotResponse(
            session_id=aggregate.session.id,
            status=aggregate.session.status,
            locale=aggregate.session.locale,
            spread_type=aggregate.session.spread_type,
            normalized_question=aggregate.session.normalized_question,
            current_reading_id=aggregate.reading.id if aggregate.reading else None,
            clarification_turn_count=self._clarification_turn_count(aggregate.messages),
            created_at=aggregate.session.created_at,
            updated_at=aggregate.session.updated_at,
            completed_at=aggregate.session.completed_at,
        )

    def get_session_result(self, session_id: str) -> ReadingResultResponse:
        aggregate = self._get_session_or_404(session_id)
        if aggregate.session.status not in self._TERMINAL_STATUSES:
            raise AppError.invalid_state_transition(
                "Session is not ready to return a result.",
                details={
                    "session_id": session_id,
                    "current_status": aggregate.session.status.value,
                },
            )

        if aggregate.reading is None:
            raise AppError.resource_not_found(
                "Session result was not found.",
                details={"session_id": session_id},
            )
        reading_aggregate = self._repository.get_reading(aggregate.reading.id)
        if reading_aggregate is None:
            raise AppError.resource_not_found(
                "Session result was not found.",
                details={"session_id": session_id},
            )
        return TarotReadingService.to_reading_response(reading_aggregate)

    def get_session_history(self, session_id: str) -> SessionHistoryResponse:
        aggregate = self._get_session_or_404(session_id)
        return SessionHistoryResponse(
            session_id=aggregate.session.id,
            items=[
                SessionHistoryItemResponse(
                    message_id=message.id,
                    message_type=message.message_type,
                    sender_role=message.sender_role,
                    turn_index=message.turn_index,
                    content=message.content,
                    created_at=message.created_at,
                )
                for message in aggregate.messages
            ],
        )

    def _get_session_or_404(self, session_id: str) -> SessionAggregate:
        aggregate = self._repository.get_session(session_id)
        if aggregate is None:
            raise AppError.resource_not_found("Session was not found.", details={"session_id": session_id})
        return aggregate

    @staticmethod
    def _ensure_state(
        *,
        aggregate: SessionAggregate,
        allowed_statuses: set[WorkflowStatus],
        action: str,
    ) -> None:
        if aggregate.session.status in allowed_statuses:
            return
        raise AppError.invalid_state_transition(
            f"Session cannot perform {action} in its current status.",
            details={
                "session_id": aggregate.session.id,
                "current_status": aggregate.session.status.value,
                "allowed_statuses": sorted(status.value for status in allowed_statuses),
            },
        )

    @staticmethod
    def _require_clarification_output(state: TarotWorkflowState):
        if state.clarification_output is None:
            raise AppError.dependency_unavailable(
                "Workflow clarification output was missing.",
                details={"session_id": state.session_id, "workflow_status": state.status.value},
            )
        return state.clarification_output

    def _compose_follow_up_question(
        self,
        *,
        aggregate: SessionAggregate,
        new_answer: str,
    ) -> str:
        original_question = self._required_message(
            aggregate.messages,
            SessionMessageType.ORIGINAL_QUESTION,
        ).content
        existing_answers = [
            message.content
            for message in aggregate.messages
            if message.message_type is SessionMessageType.CLARIFICATION_ANSWER
        ]
        all_answers = [*existing_answers, new_answer]
        bullet_list = "\n".join(f"- {item}" for item in all_answers)
        return f"原始问题：{original_question}\n补充信息：\n{bullet_list}"

    @staticmethod
    def _required_message(
        messages: list[SessionMessageRecord],
        message_type: SessionMessageType,
    ) -> SessionMessageRecord:
        for message in messages:
            if message.message_type is message_type:
                return message
        raise AppError.resource_not_found(
            "Required session message was not found.",
            details={"message_type": message_type.value},
        )

    @staticmethod
    def _latest_message(
        messages: list[SessionMessageRecord],
        message_type: SessionMessageType,
    ) -> SessionMessageRecord | None:
        matches = [message for message in messages if message.message_type is message_type]
        if not matches:
            return None
        return max(matches, key=lambda message: message.turn_index)

    @staticmethod
    def _clarification_turn_count(messages: list[SessionMessageRecord]) -> int:
        return sum(1 for message in messages if message.message_type is SessionMessageType.CLARIFICATION_ANSWER)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
