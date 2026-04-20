from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_tarot_session_service
from app.application.services import TarotSessionService
from app.schemas.api.readings import ReadingResultResponse
from app.schemas.api.sessions import (
    CreateSessionRequest,
    CreateSessionResponse,
    RunSessionRequest,
    SessionHistoryResponse,
    SessionSnapshotResponse,
    SubmitClarificationRequest,
    SubmitClarificationResponse,
    SubmitQuestionRequest,
    SubmitQuestionResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse, summary="Create a tarot session")
def create_session(
    request: CreateSessionRequest,
    service: TarotSessionService = Depends(get_tarot_session_service),
) -> CreateSessionResponse:
    return service.create_session(request)


@router.post(
    "/{session_id}/question",
    response_model=SubmitQuestionResponse,
    summary="Submit the original question for a session",
)
def submit_question(
    session_id: str,
    request: SubmitQuestionRequest,
    service: TarotSessionService = Depends(get_tarot_session_service),
) -> SubmitQuestionResponse:
    return service.submit_question(session_id, request)


@router.post(
    "/{session_id}/clarifications",
    response_model=SubmitClarificationResponse,
    summary="Submit a clarification answer for a session",
)
def submit_clarification(
    session_id: str,
    request: SubmitClarificationRequest,
    service: TarotSessionService = Depends(get_tarot_session_service),
) -> SubmitClarificationResponse:
    return service.submit_clarification(session_id, request)


@router.post(
    "/{session_id}/run",
    response_model=ReadingResultResponse,
    summary="Run a ready session through the tarot workflow",
)
def run_session(
    session_id: str,
    request: RunSessionRequest,
    service: TarotSessionService = Depends(get_tarot_session_service),
) -> ReadingResultResponse:
    return service.run_session(session_id)


@router.get(
    "/{session_id}",
    response_model=SessionSnapshotResponse,
    summary="Get the current session snapshot",
)
def get_session(
    session_id: str,
    service: TarotSessionService = Depends(get_tarot_session_service),
) -> SessionSnapshotResponse:
    return service.get_session_snapshot(session_id)


@router.get(
    "/{session_id}/result",
    response_model=ReadingResultResponse,
    summary="Get the final result of a completed session",
)
def get_session_result(
    session_id: str,
    service: TarotSessionService = Depends(get_tarot_session_service),
) -> ReadingResultResponse:
    return service.get_session_result(session_id)


@router.get(
    "/{session_id}/history",
    response_model=SessionHistoryResponse,
    summary="Get the ordered session message history",
)
def get_session_history(
    session_id: str,
    service: TarotSessionService = Depends(get_tarot_session_service),
) -> SessionHistoryResponse:
    return service.get_session_history(session_id)
