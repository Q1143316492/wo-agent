"""当前这次工具执行的取消事件。循环传入，会起进程的 runner 来读。"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar

_cancel: ContextVar[asyncio.Event | None] = ContextVar("wo_agent_tool_cancel", default=None)


def tool_cancel() -> asyncio.Event | None:
    return _cancel.get()


def bind_tool_cancel(event: asyncio.Event | None):
    return _cancel.set(event)


def reset_tool_cancel(token) -> None:
    _cancel.reset(token)
