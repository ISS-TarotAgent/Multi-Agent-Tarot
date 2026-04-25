from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.deps import get_settings_dep
from app.infrastructure.config.settings import AppSettings
from app.infrastructure.db import get_engine
from app.schemas.api.health import DependencyStatus, HealthResponse

router = APIRouter(tags=["health"])


def _check_database() -> DependencyStatus:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return DependencyStatus(status="ok")
    except OperationalError as exc:
        return DependencyStatus(status="unavailable", detail=str(exc.orig))


def _check_openai(settings: AppSettings) -> DependencyStatus:
    if settings.openai_api_key:
        return DependencyStatus(status="ok")
    return DependencyStatus(status="unavailable", detail="OPENAI_API_KEY not configured")


def _check_langfuse(settings: AppSettings) -> DependencyStatus:
    if not settings.langfuse_enabled:
        return DependencyStatus(status="ok", detail="disabled")
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        return DependencyStatus(status="ok")
    return DependencyStatus(status="unavailable", detail="Langfuse enabled but keys not configured")


@router.get("/health", response_model=HealthResponse, summary="Backend liveness and readiness check")
def get_health(settings: AppSettings = Depends(get_settings_dep)) -> HealthResponse:
    deps = {
        "database": _check_database(),
        "openai": _check_openai(settings),
        "langfuse": _check_langfuse(settings),
    }
    overall = "ok" if all(d.status == "ok" for d in deps.values()) else "degraded"
    return HealthResponse(
        status=overall,
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        dependencies=deps,
    )
