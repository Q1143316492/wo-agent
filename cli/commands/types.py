"""命令的数据类型。handler 返回意图，不 import Textual。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OutcomeKind = Literal["quit", "clear", "help", "unknown", "note", "new_session", "load_session"]


@dataclass(frozen=True)
class ParsedCommand:
    """``name`` 不含斜杠；``raw_input`` 是名字后面的原文（含前导空白）。"""

    name: str
    raw_input: str


@dataclass
class CommandContext:
    """handler 需要的宿主对象。字段都可以空，核心命令用不到。"""

    store: object | None = None
    session: object | None = None
    workspace: object | None = None
    sessions_dir: object | None = None


@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    aliases: tuple[str, ...] = ()
    handler: object | None = None


@dataclass(frozen=True)
class Suggestion:
    """补全一项。``name`` 不含斜杠，是写回输入框的词。"""

    name: str
    description: str


@dataclass(frozen=True)
class CommandOutcome:
    kind: OutcomeKind
    text: str = ""
    session_id: str = ""
