"""宿主侧观察工具执行：预览、折叠、包装 ``execute``。不进循环。"""

from __future__ import annotations

import json
from collections.abc import Callable

from tools import ToolExecutor, ToolResult

PREVIEW_CHARS = 80
TAIL_LINES = 8

OnStart = Callable[[str, str], None]
OnEnd = Callable[[str, str, bool], None]


def _parse_args(arguments: str) -> dict:
    if not arguments:
        return {}
    try:
        data = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def argument_preview(name: str, arguments: str) -> str:
    data = _parse_args(arguments)
    if name == "bash":
        raw = data.get("command")
        return raw if isinstance(raw, str) else ""
    if name in ("grep", "glob"):
        parts: list[str] = []
        pattern = data.get("pattern")
        path = data.get("path")
        if isinstance(pattern, str):
            parts.append(pattern)
        if isinstance(path, str):
            parts.append(path)
        return " ".join(parts)
    if name in ("read", "write", "edit"):
        path = data.get("file_path")
        return path if isinstance(path, str) else ""
    return ""


def clip_preview(text: str, limit: int = PREVIEW_CHARS) -> str:
    one = " ".join(text.split())
    if len(one) <= limit:
        return one
    if limit <= 1:
        return "…"
    return one[: limit - 1] + "…"


def collapse_body(text: str, tail_lines: int = TAIL_LINES) -> str:
    if not text:
        return text
    lines = text.splitlines()
    if len(lines) <= tail_lines:
        return text
    return "\n".join(lines[-tail_lines:])


def header_line(name: str, arguments: str, *, clipped: bool = True) -> str:
    preview = argument_preview(name, arguments)
    shown = clip_preview(preview) if clipped else " ".join(preview.split())
    if shown:
        return f"{name}  {shown}"
    return name


def result_text(result: ToolResult) -> str:
    parts: list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def wrap_tools(inner: ToolExecutor, on_start: OnStart | None, on_end: OnEnd | None) -> ToolExecutor:
    if on_start is None or on_end is None:
        return inner
    return ObservingToolExecutor(inner, on_start, on_end)


def format_tool_card(
    name: str,
    arguments: str,
    result: str | None,
    *,
    expanded: bool,
) -> str:
    header = header_line(name, arguments, clipped=not expanded)
    line = f"●  {header}"
    if result is None:
        return line
    body = result if expanded else collapse_body(result)
    if not body:
        return line
    return f"{line}\n{body}"


class ObservingToolExecutor:
    """把开始/结束通知给宿主；schema 和结果原样转交。"""

    def __init__(self, inner: ToolExecutor, on_start: OnStart, on_end: OnEnd) -> None:
        self._inner = inner
        self._on_start = on_start
        self._on_end = on_end

    def schemas(self):
        return self._inner.schemas()

    async def execute(self, name: str, arguments: str, cancel=None) -> ToolResult:
        self._on_start(name, arguments)
        result = await self._inner.execute(name, arguments, cancel=cancel)
        self._on_end(name, result_text(result), result.is_error)
        return result
