"""Provider 缝。agent 层只依赖本模块。

provider 把 ``LLMRequest`` 变成一串分片。终止永远是 ``finish`` 分片：
成功原因是 ``stop`` / ``tool-calls`` / ``max-tokens``；失败是 ``error`` /
``aborted``，携带结构化失败。provider 绝不在流上抛出异常。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Protocol

from .types import LLMMessage, StreamChunk, ToolSchema


@dataclass(frozen=True)
class LLMRequest:
    provider: str
    model: str
    messages: list[LLMMessage]
    max_tokens: int | None = None
    temperature: float | None = None
    reasoning_effort: str | None = None
    stop: tuple[str, ...] = ()
    tools: tuple[ToolSchema, ...] = ()


class LLMProvider(Protocol):
    async def stream(
        self,
        request: LLMRequest,
        signal: asyncio.Event | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """为一次调用流出分片。

        ``signal`` 是协作式取消：一旦被置位，provider 停止并发出 kind 为
        ``aborted`` 的终止 ``finish``。
        """
        ...
