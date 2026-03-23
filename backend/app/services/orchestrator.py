"""Wrapper that connects FastAPI handlers to the LangGraph workflow."""

from __future__ import annotations

from agent.workflows import orchestrator
from agent.core import schemas


class TarotOrchestrator:
    """High-level service for triggering the multi-agent workflow."""

    def __init__(self) -> None:
        # TODO: store built workflow, model gateway refs, tracing config
        raise NotImplementedError("TarotOrchestrator wiring is pending implementation")

    async def start_session(self, payload: schemas.ClarificationRequest) -> schemas.OrchestratorState:
        """TODO: call LangGraph workflow to run full pipeline."""

        raise NotImplementedError

    async def continue_clarification(self, session_id: str, message: str) -> schemas.OrchestratorState:
        """TODO: support iterative clarification path."""

        raise NotImplementedError
