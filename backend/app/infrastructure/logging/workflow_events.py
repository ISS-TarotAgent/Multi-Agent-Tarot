from __future__ import annotations

import logging

from app.domain.enums import TraceEventStatus
from app.schemas.workflow.trace_event import TraceEventPayload

logger = logging.getLogger("app.workflow")


def log_trace_event(
    *,
    session_id: str,
    reading_id: str | None,
    event: TraceEventPayload,
) -> None:
    extra = {
        "session_id": session_id,
        "reading_id": reading_id,
        "trace_event_id": event.event_id,
        "step_name": event.step_name,
        "event_status": event.event_status.value,
        "attempt_no": event.attempt_no,
        "latency_ms": event.latency_ms,
        "error_code": event.error_code,
        "trace_payload": event.payload,
    }

    if event.event_status is TraceEventStatus.FAILED:
        logger.error("workflow_trace_event", extra=extra)
        return
    if event.event_status is TraceEventStatus.FALLBACK:
        logger.warning("workflow_trace_event", extra=extra)
        return
    logger.info("workflow_trace_event", extra=extra)
