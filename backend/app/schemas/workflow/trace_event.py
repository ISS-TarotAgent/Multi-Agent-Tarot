from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.enums import TraceEventStatus
from app.schemas.workflow.common import WorkflowSchema


class TraceEventPayload(WorkflowSchema):
    event_id: str
    step_name: str
    event_status: TraceEventStatus
    attempt_no: int
    latency_ms: int | None = None
    error_code: str | None = None
    payload: dict[str, Any]
    created_at: datetime
