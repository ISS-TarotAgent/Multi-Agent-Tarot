"""Shared FastAPI dependencies (DB sessions, orchestrator, etc.)."""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends


async def get_db() -> AsyncIterator[None]:
    """Provide a database session (placeholder).

    TODO:
        - integrate SQLAlchemy async Session
        - wire connection settings from app.core.config
        - ensure sessions close/rollback on exit
    """

    raise NotImplementedError("Database dependency not wired yet")


async def get_workflow():
    """Return a handle to the LangGraph workflow orchestrator.

    TODO:
        - call agent.workflows.build_tarot_workflow()
        - cache singleton per-process
        - expose tracing hooks for observability
    """

    raise NotImplementedError("Workflow dependency not wired yet")
