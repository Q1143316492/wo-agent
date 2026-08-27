"""面向模型的 ``read`` / ``write`` / ``edit`` / ``bash``。

文件三件套只通过 ``WorkspaceStore`` 碰盘。``bash`` 只通过 ``BashRunner`` 起进程。
"""

from __future__ import annotations

from pathlib import Path

from llm.types import TextBlock
from tools import ToolDefinition

from .errors import WorkspaceError
from .read_render import READ_LIMIT, build_window, format_read_output
from .shell import (
    DEFAULT_TIMEOUT_S,
    MAX_TIMEOUT_S,
    BashResult,
    BashRunner,
    format_bash_output,
    truncate_tail,
)
from .text import WorkspaceStore


def _require_str(args: dict, name: str) -> str:
    value = args.get(name)
    if not isinstance(value, str):
        raise WorkspaceError(f"{name} must be a string", "INVALID_ARGUMENT")
    return value


def _optional_positive_int(args: dict, name: str, default: int, maximum: int | None = None) -> int:
    value = args.get(name)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkspaceError(f"{name} must be a positive integer", "INVALID_ARGUMENT")
    if value < 1:
        raise WorkspaceError(f"{name} must be a positive integer", "INVALID_ARGUMENT")
    if maximum is not None and value > maximum:
        raise WorkspaceError(f"{name} must be less than or equal to {maximum}", "INVALID_ARGUMENT")
    return value


def _optional_bool(args: dict, name: str, default: bool = False) -> bool:
    value = args.get(name)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise WorkspaceError(f"{name} must be a boolean", "INVALID_ARGUMENT")
    return value


def make_read_tool(store: WorkspaceStore) -> ToolDefinition:
    async def execute(args: dict) -> list:
        file_path = _require_str(args, "file_path")
        offset = _optional_positive_int(args, "offset", 1)
        limit = _optional_positive_int(args, "limit", READ_LIMIT, READ_LIMIT)
        display, text = store.read_text(file_path)
        window = build_window(text, display, offset, limit)
        return [TextBlock(text=format_read_output(display, window))]

    return ToolDefinition(
        name="read",
        description="Read a UTF-8 text file and return line-numbered content.",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to read, relative to the workspace root.",
                },
                "offset": {
                    "type": "integer",
                    "description": "1-based first line to return. Defaults to 1.",
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of lines to return. Defaults to {READ_LIMIT}.",
                },
            },
            "required": ["file_path"],
        },
        execute=execute,
    )


def make_write_tool(store: WorkspaceStore) -> ToolDefinition:
    async def execute(args: dict) -> list:
        file_path = _require_str(args, "file_path")
        content = _require_str(args, "content")
        display, operation = store.write_text(file_path, content)
        verb = "Created" if operation == "create" else "Updated"
        text = f"<path>{display}</path>\n<type>file</type>\n<content>\n{verb} file\n</content>"
        return [TextBlock(text=text)]

    return ToolDefinition(
        name="write",
        description="Create or fully replace a UTF-8 text file.",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to write, relative to the workspace root.",
                },
                "content": {
                    "type": "string",
                    "description": "Full UTF-8 text content to write.",
                },
            },
            "required": ["file_path", "content"],
        },
        execute=execute,
    )


def make_edit_tool(store: WorkspaceStore) -> ToolDefinition:
    async def execute(args: dict) -> list:
        file_path = _require_str(args, "file_path")
        old_string = _require_str(args, "old_string")
        new_string = _require_str(args, "new_string")
        if old_string == new_string:
            raise WorkspaceError("old_string and new_string must differ", "NOOP_EDIT")
        replace_all = _optional_bool(args, "replace_all", False)
        display = store.edit_text(file_path, old_string, new_string, replace_all)
        if replace_all:
            text = f"The file {display} has been updated. All occurrences were successfully replaced."
        else:
            text = f"The file {display} has been updated successfully."
        return [TextBlock(text=text)]

    return ToolDefinition(
        name="edit",
        description="Edit an existing UTF-8 text file by replacing literal text.",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to edit, relative to the workspace root.",
                },
                "old_string": {
                    "type": "string",
                    "description": "Literal text to replace. Must match exactly.",
                },
                "new_string": {
                    "type": "string",
                    "description": "Literal replacement text. Use an empty string to delete the match.",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all matches. Defaults to false; when false, old_string must appear exactly once.",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        },
        execute=execute,
    )


def _optional_timeout(args: dict, default: float) -> float:
    value = args.get("timeout")
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorkspaceError("timeout must be a positive number of seconds", "INVALID_ARGUMENT")
    if value <= 0:
        raise WorkspaceError("timeout must be a positive number of seconds", "INVALID_ARGUMENT")
    if value > MAX_TIMEOUT_S:
        raise WorkspaceError(f"timeout must be less than or equal to {MAX_TIMEOUT_S}", "INVALID_ARGUMENT")
    return float(value)


def make_bash_tool(cwd: Path, runner: BashRunner, default_timeout_s: float = DEFAULT_TIMEOUT_S) -> ToolDefinition:
    async def execute(args: dict) -> list:
        command = _require_str(args, "command").strip()
        if not command:
            raise WorkspaceError("command must be a non-empty string", "INVALID_ARGUMENT")
        timeout_s = _optional_timeout(args, default_timeout_s)
        if not cwd.is_dir():
            raise WorkspaceError(f"working directory does not exist: {cwd}", "NOT_FOUND")
        result = await runner.run(command, cwd, timeout_s)
        trimmed, truncated = truncate_tail(result.output)
        shown = BashResult(exit_code=result.exit_code, output=trimmed, timed_out=result.timed_out)
        return [TextBlock(text=format_bash_output(cwd, shown, truncated))]

    return ToolDefinition(
        name="bash",
        description=(
            "Execute a bash command in the workspace root. Returns stdout and stderr. "
            "Not sandboxed: the command can access paths outside the workspace. "
            "Output is truncated to the last 2000 lines or 50KB. "
            "Optional timeout in seconds (default 30, max 300)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Bash command to execute in the workspace root.",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds. Defaults to 30; maximum 300.",
                },
            },
            "required": ["command"],
        },
        execute=execute,
    )
