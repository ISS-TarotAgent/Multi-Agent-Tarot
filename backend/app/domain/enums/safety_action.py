from __future__ import annotations

from enum import StrEnum


class SafetyAction(StrEnum):
    PASSTHROUGH = "PASSTHROUGH"
    REWRITE = "REWRITE"
    BLOCK_AND_FALLBACK = "BLOCK_AND_FALLBACK"
