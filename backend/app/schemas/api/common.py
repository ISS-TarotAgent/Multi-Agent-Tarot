from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(ApiSchema):
    error_code: str
    message: str
    details: dict[str, Any] | None = None
    trace_id: str | None = None
    retryable: bool
