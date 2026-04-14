from __future__ import annotations

from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from agent.workflows import TarotReflectionWorkflow
from app.api.errors import AppError
from app.domain.enums import SafetyAction, TraceEventStatus
from app.domain.repositories import ReadingAggregate, TarotReadingRepository
from app.infrastructure.observability import NoOpWorkflowObserver
from app.schemas.api.readings import (
    CreateReadingRequest,
    ReadingCardPayload,
    ReadingClarificationPayload,
    ReadingQuestionPayload,
    ReadingResultResponse,
    ReadingSafetyPayload,
    ReadingSynthesisPayload,
    ReadingTraceSummaryPayload,
)
from app.schemas.api.traces import ReadingTraceEventPayload, ReadingTraceResponse


class TarotReadingService:
    """Coordinates the phase-2 reading workflow and API serialization."""

    def __init__(
        self,
        repository: TarotReadingRepository,
        workflow: TarotReflectionWorkflow | None = None,
        observer: NoOpWorkflowObserver | None = None,
    ) -> None:
        self._repository = repository
        self._observer = observer or NoOpWorkflowObserver()
        self._workflow = workflow or TarotReflectionWorkflow(observer=self._observer)

    def create_reading(self, request: CreateReadingRequest) -> ReadingResultResponse:
        session_id = str(uuid4())
        reading_id = str(uuid4())

        with self._observer.observe_operation(
            name="tarot.reading.create",
            session_id=session_id,
            reading_id=reading_id,
            input_payload={
                "question": request.question,
                "locale": request.locale,
                "spread_type": request.spread_type.value,
            },
            metadata={"client_request_id": request.client_request_id},
        ) as operation:
            try:
                self._repository.bootstrap_reading(
                    session_id=session_id,
                    reading_id=reading_id,
                    raw_question=request.question,
                    locale=request.locale,
                    spread_type=request.spread_type,
                    created_at=self._now(),
                )
                state = self._workflow.run(
                    session_id=session_id,
                    reading_id=reading_id,
                    raw_question=request.question,
                    locale=request.locale,
                    spread_type=request.spread_type,
                    client_request_id=request.client_request_id,
                    metadata=request.metadata,
                    persistence_handler=self._repository.save_workflow_result,
                )
            except SQLAlchemyError as exc:
                operation.failure(
                    error_code="DEPENDENCY_UNAVAILABLE",
                    message="Database operation failed.",
                    metadata={"reason": str(exc)},
                )
                raise AppError.dependency_unavailable("Database operation failed.", details={"reason": str(exc)}) from exc

            aggregate = self._repository.get_reading(reading_id)
            if aggregate is None:
                operation.failure(
                    error_code="RESOURCE_NOT_FOUND",
                    message="Reading not found after creation.",
                    metadata={"reading_id": reading_id},
                )
                raise AppError.resource_not_found(
                    "Reading not found after creation.",
                    details={"reading_id": reading_id},
                )

            response = self.to_reading_response(aggregate)
            operation.success(
                output={
                    "status": response.status.value,
                    "trace_event_count": response.trace_summary.event_count,
                }
            )
            return response

    def get_reading(self, reading_id: str) -> ReadingResultResponse:
        aggregate = self._repository.get_reading(reading_id)
        if aggregate is None:
            raise AppError.resource_not_found("Reading was not found.", details={"reading_id": reading_id})
        return self.to_reading_response(aggregate)

    def get_reading_trace(self, reading_id: str) -> ReadingTraceResponse:
        aggregate = self._repository.get_reading(reading_id)
        if aggregate is None:
            raise AppError.resource_not_found("Reading trace was not found.", details={"reading_id": reading_id})
        return ReadingTraceResponse(
            reading_id=aggregate.reading.id,
            session_id=aggregate.session.id,
            status=aggregate.reading.status,
            events=[
                ReadingTraceEventPayload(
                    event_id=event.id,
                    step_name=event.step_name,
                    event_status=event.event_status,
                    attempt_no=event.attempt_no,
                    latency_ms=event.latency_ms,
                    error_code=event.error_code,
                    payload_summary=event.trace_payload,
                    created_at=event.created_at,
                )
                for event in aggregate.trace_events
            ],
        )

    @staticmethod
    def to_reading_response(aggregate: ReadingAggregate) -> ReadingResultResponse:
        trace_summary = ReadingTraceSummaryPayload(
            event_count=len(aggregate.trace_events),
            warning_count=sum(
                1 for event in aggregate.trace_events if event.event_status is TraceEventStatus.FALLBACK
            ),
            error_count=sum(1 for event in aggregate.trace_events if event.event_status is TraceEventStatus.FAILED),
        )
        clarification_required = aggregate.clarification_message is not None
        return ReadingResultResponse(
            reading_id=aggregate.reading.id,
            session_id=aggregate.session.id,
            status=aggregate.reading.status,
            locale=aggregate.session.locale,
            spread_type=aggregate.session.spread_type,
            question=ReadingQuestionPayload(
                raw_question=aggregate.original_question_message.content,
                normalized_question=aggregate.reading.normalized_question,
            ),
            clarification=ReadingClarificationPayload(
                required=clarification_required,
                question_text=aggregate.clarification_message.content if aggregate.clarification_message else None,
                answer_text=None,
            ),
            cards=[
                ReadingCardPayload(
                    position=card.position,
                    card_code=card.card_code,
                    card_name=card.card_name,
                    orientation=card.orientation,
                    interpretation=card.interpretation,
                )
                for card in aggregate.cards
            ],
            synthesis=ReadingSynthesisPayload(
                summary=aggregate.reading.summary,
                action_advice=aggregate.reading.action_advice,
                reflection_question=aggregate.reading.reflection_question,
            ),
            safety=ReadingSafetyPayload(
                risk_level=aggregate.safety_review.risk_level if aggregate.safety_review else aggregate.reading.risk_level,
                action_taken=(
                    aggregate.safety_review.action_taken
                    if aggregate.safety_review
                    else SafetyAction.PASSTHROUGH
                ),
                review_notes=aggregate.safety_review.review_notes if aggregate.safety_review else None,
            ),
            trace_summary=trace_summary,
            created_at=aggregate.reading.created_at,
            completed_at=aggregate.reading.completed_at,
        )

    @staticmethod
    def _now():
        from datetime import UTC, datetime

        return datetime.now(UTC)
