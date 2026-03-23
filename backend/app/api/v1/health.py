"""Health and metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Backend liveness probe")
async def health_check() -> dict[str, str]:
    """TODO: return real readiness data (DB, workflow, model gateway)."""

    raise NotImplementedError("health_check endpoint not implemented yet")


@router.get("/version", summary="Service version info")
async def version_check() -> dict[str, str]:
    """TODO: include git SHA, model versions, prompt pack hash, etc."""

    raise NotImplementedError("version_check endpoint not implemented yet")
