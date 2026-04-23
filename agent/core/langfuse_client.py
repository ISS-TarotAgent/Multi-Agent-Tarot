"""Langfuse singleton — shared by ModelGateway and WorkflowObserver.

Initialised once on first call; returns None when env vars are absent so all
callers can safely do ``if lf := get_langfuse()``.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langfuse import Langfuse

logger = logging.getLogger(__name__)

_client: Any = None
_initialised = False


def get_langfuse() -> "Langfuse | None":
    global _client, _initialised
    if _initialised:
        return _client
    _initialised = True

    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return None

    try:
        from langfuse import Langfuse  # noqa: PLC0415
        _client = Langfuse()  # reads LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST from env
        logger.info("langfuse_client_initialised", extra={"host": os.getenv("LANGFUSE_HOST", "cloud")})
    except Exception as exc:  # noqa: BLE001
        logger.warning("langfuse_client_init_failed", extra={"error": str(exc)})

    return _client
