"""``read`` 的行窗口与模型可见包络。纯函数，不碰盘。

格式对齐 dsh ``tool-fs`` 的 ``formatReadOutput``：``<path>`` / 行号 / footer。
行号从 1 起；行内 Tab 原样保留，便于把原文抄进 ``edit`` 的 ``old_string``。
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import WorkspaceError

READ_LIMIT = 2000
READ_MAX_LINE_LENGTH = 2000
READ_MAX_BYTES = 50 * 1024


@dataclass(frozen=True)
class FileTextLine:
    number: int
    text: str


@dataclass(frozen=True)
class ReadWindow:
    offset: int
    lines: tuple[FileTextLine, ...]
    total_lines: int
    truncated_by_bytes: bool


def _truncate_line(line: str, max_line_length: int) -> str:
    if len(line) <= max_line_length:
        return line
    return f"{line[:max_line_length]}... (line truncated to {max_line_length} chars)"


def split_lines(text: str) -> list[str]:
    """按 ``\\n`` 拆行并去掉行尾 ``\\r``；保留末行即使文件无结尾换行。"""
    if text == "":
        return []
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return [line[:-1] if line.endswith("\r") else line for line in parts]


def build_window(
    text: str,
    display: str,
    offset: int,
    limit: int,
    max_line_length: int = READ_MAX_LINE_LENGTH,
    max_bytes: int = READ_MAX_BYTES,
) -> ReadWindow:
    lines = split_lines(text)
    total = len(lines)
    if offset > total and not (total == 0 and offset == 1):
        raise WorkspaceError(f'offset {offset} is out of range for "{display}" ({total} lines)', "OFFSET_OUT_OF_RANGE")

    selected: list[FileTextLine] = []
    output_bytes = 0
    truncated = False
    for index, raw in enumerate(lines, start=1):
        if index < offset:
            continue
        if len(selected) >= limit:
            break
        rendered = _truncate_line(raw, max_line_length)
        extra = len(rendered.encode("utf-8")) + (1 if selected else 0)
        if output_bytes + extra > max_bytes:
            truncated = True
            break
        output_bytes += extra
        selected.append(FileTextLine(number=index, text=rendered))
    return ReadWindow(offset=offset, lines=tuple(selected), total_lines=total, truncated_by_bytes=truncated)


def format_read_output(display: str, window: ReadWindow) -> str:
    end_line = window.lines[-1].number if window.lines else max(0, window.offset - 1)
    if window.truncated_by_bytes:
        footer = f"(Output capped. Showing lines {window.offset}-{end_line}. Use offset={end_line + 1} to continue.)"
    elif end_line < window.total_lines:
        footer = (
            f"(Showing lines {window.offset}-{end_line} of {window.total_lines}. "
            f"Use offset={end_line + 1} to continue.)"
        )
    else:
        footer = f"(End of file - total {window.total_lines} lines)"
    body = f"{chr(10).join(f'{line.number}: {line.text}' for line in window.lines)}\n\n{footer}" if window.lines else footer
    return f"<path>{display}</path>\n<type>file</type>\n<content>\n{body}\n</content>"
