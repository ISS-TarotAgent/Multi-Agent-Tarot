from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.domain.enums import TraceEventStatus
from app.infrastructure.logging.workflow_events import log_trace_event
from app.schemas.workflow.trace_event import TraceEventPayload


def test_log_trace_event_uses_warning_level_for_fallback(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="app.workflow")

    event = TraceEventPayload(
        event_id="trace-event-1",
        step_name="clarifier",
        event_status=TraceEventStatus.FALLBACK,
        attempt_no=1,
        latency_ms=15,
        error_code="CLARIFIER_FALLBACK_TO_RAW",
        payload={"reason": "clarifier_failed"},
        created_at=datetime.now(UTC),
    )

    log_trace_event(session_id="session-1", reading_id=None, event=event)

    record = next(record for record in caplog.records if record.message == "workflow_trace_event")
    assert record.levelname == "WARNING"
    assert record.session_id == "session-1"
    assert record.reading_id is None
    assert record.step_name == "clarifier"
    assert record.error_code == "CLARIFIER_FALLBACK_TO_RAW"


def test_log_trace_event_uses_error_level_for_failed_step(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.workflow")

    event = TraceEventPayload(
        event_id="trace-event-2",
        step_name="draw_interpreter",
        event_status=TraceEventStatus.FAILED,
        attempt_no=2,
        latency_ms=42,
        error_code="SCHEMA_VALIDATION_FAILED",
        payload={"message": "field required"},
        created_at=datetime.now(UTC),
    )

    log_trace_event(session_id="session-2", reading_id="reading-2", event=event)

    record = next(record for record in caplog.records if record.message == "workflow_trace_event")
    assert record.levelname == "ERROR"
    assert record.reading_id == "reading-2"
    assert record.step_name == "draw_interpreter"
    assert record.attempt_no == 2
