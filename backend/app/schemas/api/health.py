from typing import Literal

from app.schemas.api.common import ApiSchema


class DependencyStatus(ApiSchema):
    status: Literal["ok", "unavailable"]
    detail: str | None = None


class HealthResponse(ApiSchema):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str
    timestamp: str
    dependencies: dict[str, DependencyStatus]
