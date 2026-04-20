from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.enums import TraceEventStatus, WorkflowStatus
from app.schemas.api.common import ApiSchema


class ReadingTraceEventPayload(ApiSchema):
    event_id: str
    step_name: str
    event_status: TraceEventStatus
    attempt_no: int
    latency_ms: int | None = None
    error_code: str | None = None
    payload_summary: dict[str, Any]
    created_at: datetime


class ReadingTraceResponse(ApiSchema):
    reading_id: str
    session_id: str
    status: WorkflowStatus
    events: list[ReadingTraceEventPayload]
