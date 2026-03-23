"""Primary endpoints for the tarot reflection workflow."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.models import dto

router = APIRouter()


@router.post("/sessions", response_model=dto.SessionResponse, summary="Start a tarot session")
async def start_session(payload: dto.SessionRequest, workflow = Depends(deps.get_workflow)):
    """Kick off clarification + draw workflow for a fresh session.

    TODO:
        - validate payload against security policy
        - call workflow with ClarificationRequest
        - persist session metadata via storage service
    """

    raise NotImplementedError("start_session endpoint not implemented yet")


@router.post("/sessions/{session_id}/clarify", response_model=dto.ClarificationResponse)
async def clarify(session_id: str, payload: dto.ClarificationMessage, workflow = Depends(deps.get_workflow)):
    """Allow iterative clarification rounds.

    TODO:
        - fetch session context from storage
        - feed message to Clarifier node
        - return updated ClarificationResult structure
    """

    raise NotImplementedError("clarify endpoint not implemented yet")


@router.get("/sessions/{session_id}", response_model=dto.SessionDetail)
async def get_session(session_id: str, db = Depends(deps.get_db)):
    """Fetch historical tarot session data for frontend display.

    TODO:
        - load session record + card draws + safety outcome
        - enforce access control (e.g., same user)
    """

    raise NotImplementedError("get_session endpoint not implemented yet")
