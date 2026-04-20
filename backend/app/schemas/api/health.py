from typing import Literal

from app.schemas.api.common import ApiSchema


class HealthResponse(ApiSchema):
    status: Literal["ok"]
    service: str
    version: str
    environment: str
    timestamp: str
