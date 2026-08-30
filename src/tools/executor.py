"""工具执行：注册表 + 守卫管线，实现 `ToolExecutor` 缝。

管线（对齐 dsh-tools 的结构）：注册表查找 → 守卫（单调拒绝，只能拒绝不能
放行）→ 解析参数 → 执行 → 错误处理。错误不抛出，而是变成 is_error 结果，
由循环包装成持久的 tool-result 消息。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Protocol

from llm.types import ContentBlock, TextBlock, ToolSchema

from .cancel import bind_tool_cancel, reset_tool_cancel
from .definition import ToolDefinition


@dataclass(frozen=True)
class ToolResult:
    """一次工具调用的模型可见结果。"""

    content: list[ContentBlock]
    is_error: bool = False


class ToolGuard(Protocol):
    """执行前守卫：返回拒绝理由或 None。单调性——只能拒绝，不能放行。"""

    async def check(self, name: str, arguments: str) -> str | None: ...


class ToolExecutor(Protocol):
    """工具执行缝：给模型看 schema，执行时跑管线。"""

    def schemas(self) -> list[ToolSchema]: ...
    async def execute(
        self, name: str, arguments: str, cancel: asyncio.Event | None = None
    ) -> ToolResult: ...


def _error_block(message: str) -> list[ContentBlock]:
    return [TextBlock(text=json.dumps({"error": message}, ensure_ascii=False))]


class RegistryToolExecutor:
    """持有工具定义与守卫，按管线执行。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._guards: list[ToolGuard] = []

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def add_guard(self, guard: ToolGuard) -> None:
        self._guards.append(guard)

    def schemas(self) -> list[ToolSchema]:
        return [tool.schema for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        arguments: str,
        cancel: asyncio.Event | None = None,
    ) -> ToolResult:
        token = bind_tool_cancel(cancel)
        try:
            return await self._execute(name, arguments)
        finally:
            reset_tool_cancel(token)

    async def _execute(self, name: str, arguments: str) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(content=_error_block(f"unknown tool: {name}"), is_error=True)

        for guard in self._guards:
            reason = await guard.check(name, arguments)
            if reason is not None:
                return ToolResult(content=_error_block(f"denied: {reason}"), is_error=True)

        try:
            parsed = json.loads(arguments) if arguments else {}
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
            content = await tool.execute(parsed)
            return ToolResult(content=content)
        except Exception as error:
            return ToolResult(content=_error_block(str(error)), is_error=True)
