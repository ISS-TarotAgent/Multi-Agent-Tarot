"""Request/response models exposed via the API."""

from __future__ import annotations

from pydantic import BaseModel


class SessionRequest(BaseModel):
    """Payload for starting a session.

    TODO:
        - add user question, locale, mode flags
        - include client metadata (device, version)
    """

    pass


class SessionResponse(BaseModel):
    """Response body after creating a session.

    TODO:
        - return session_id, status, redirect hints
    """

    pass


class ClarificationMessage(BaseModel):
    """Incoming clarification message from frontend."""

    # TODO: add message text, optional UI hints
    pass


class ClarificationResponse(BaseModel):
    """Structured clarification result returned to the UI."""

    # TODO: map to agent.core.schemas.ClarificationResult when ready
    pass


class SessionDetail(BaseModel):
    """Aggregated tarot session view for history endpoint."""

    # TODO: include clarified question, cards, synthesis, safety data, timestamps
    pass
