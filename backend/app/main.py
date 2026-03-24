"""FastAPI entrypoint (Python 3.12 target)."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1 import health, tarot

app = FastAPI(title="Multi-Agent Tarot Backend", version="0.1.0")


# Router registration happens here so uvicorn imports stay thin.
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(tarot.router, prefix="/api/v1", tags=["tarot"])


@app.on_event("startup")
async def on_startup() -> None:
    """TODO: Initialize DB pools, LangGraph workflow, logging, etc."""

    # - load configuration via app.core.config.Settings
    # - instantiate ModelGateway + workflow builder
    # - warm up observability hooks (Langfuse, JSON logs)
    raise NotImplementedError("startup hook pending implementation")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """TODO: gracefully close resources (DB, gateways, background tasks)."""

    raise NotImplementedError("shutdown hook pending implementation")
