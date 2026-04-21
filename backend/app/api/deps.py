from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services import TarotReadingService, TarotSessionService
from app.infrastructure.config.settings import AppSettings, get_settings
from app.infrastructure.db import get_db_session
from app.infrastructure.db.repositories import SqlAlchemyTarotReadingRepository
from app.infrastructure.observability import build_workflow_observer


def get_settings_dep() -> AppSettings:
    return get_settings()


def get_db_session_dep() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_tarot_reading_service(
    settings: AppSettings = Depends(get_settings_dep),
    db_session: Session = Depends(get_db_session_dep),
) -> TarotReadingService:
    from agent.workflows import build_llm_workflow
    observer = build_workflow_observer(settings)
    workflow = build_llm_workflow(observer=observer) if settings.openai_api_key else None
    return TarotReadingService(
        repository=SqlAlchemyTarotReadingRepository(db_session),
        workflow=workflow,
        observer=observer,
    )


def get_tarot_session_service(
    settings: AppSettings = Depends(get_settings_dep),
    db_session: Session = Depends(get_db_session_dep),
) -> TarotSessionService:
    observer = build_workflow_observer(settings)
    return TarotSessionService(
        repository=SqlAlchemyTarotReadingRepository(db_session),
        observer=observer,
    )
