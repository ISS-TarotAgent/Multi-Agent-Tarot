from __future__ import annotations

from enum import StrEnum


class TraceEventStatus(StrEnum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    FALLBACK = "FALLBACK"
