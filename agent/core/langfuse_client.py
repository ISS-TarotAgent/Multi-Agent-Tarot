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


# 获取Langfuse的单例模式客户端实例。
# 该函数在第一次调用时会尝试从环境变量中读取Langfuse的配置，并初始化客户端实例。
# 如果环境变量缺失或初始化失败，函数将返回None。之后的调用将直接返回已初始化的客户端实例，避免重复初始化。
def get_langfuse() -> "Langfuse | None":
    global _client, _initialised

    # 通过检查_initialised标志来确定是否已经初始化过客户端实例。如果已经初始化，直接返回_client。
    if _initialised:
        return _client
    _initialised = True

    # 检查环境变量LANGFUSE_PUBLIC_KEY和LANGFUSE_SECRET_KEY是否存在。如果缺失，函数返回None，表示无法初始化Langfuse客户端。
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return None

    try:
        from langfuse import Langfuse  # noqa: PLC0415

        _client = Langfuse()  # reads LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST from env
        logger.info("langfuse_client_initialised", extra={"host": os.getenv("LANGFUSE_HOST", "cloud")})
    except Exception as exc:  # noqa: BLE001
        logger.warning("langfuse_client_init_failed", extra={"error": str(exc)})

    return _client
