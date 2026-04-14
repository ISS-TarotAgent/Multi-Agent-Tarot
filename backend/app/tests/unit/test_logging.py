from __future__ import annotations

import json
import logging

from app.infrastructure.logging.json_formatter import JsonFormatter


def test_json_formatter_serializes_standard_and_extra_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="health_ready",
        args=(),
        exc_info=None,
    )
    record.request_id = "req_123"
    record.status_code = 200

    payload = json.loads(formatter.format(record))

    assert payload["logger"] == "app.test"
    assert payload["message"] == "health_ready"
    assert payload["request_id"] == "req_123"
    assert payload["status_code"] == 200
