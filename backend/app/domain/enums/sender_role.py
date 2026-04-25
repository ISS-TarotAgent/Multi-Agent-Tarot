from __future__ import annotations

from enum import StrEnum


class SenderRole(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
