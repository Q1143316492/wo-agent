"""把一行输入收成斜杠命令。规则对齐 dsh ``parseCommand``。"""

from __future__ import annotations

import re

from .types import ParsedCommand

# dsh: /^\/([a-z][a-z0-9_-]*)(?=$|[\t\n\r ])/
_COMMAND = re.compile(r"^/([a-z][a-z0-9_-]*)(?=$|[\t\n\r ])")


def parse_line(line: str) -> ParsedCommand | None:
    """不是斜杠命令则返回 None，交给对话循环。"""
    match = _COMMAND.match(line)
    if match is None:
        return None
    name = match.group(1)
    return ParsedCommand(name=name, raw_input=line[match.end() :])
