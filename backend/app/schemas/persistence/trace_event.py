from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.enums import TraceEventStatus
from app.schemas.persistence.common import PersistenceSchema


class TraceEventRecord(PersistenceSchema):
    id: str
    session_id: str
    reading_id: str | None = None
    step_name: str
    event_status: TraceEventStatus
    attempt_no: int
    latency_ms: int | None = None
    error_code: str | None = None
    trace_payload: dict[str, Any]
    created_at: datetime
