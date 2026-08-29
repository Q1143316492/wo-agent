"""命令的数据类型。handler 返回意图，不 import Textual。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OutcomeKind = Literal["quit", "clear", "help", "unknown"]


@dataclass(frozen=True)
class ParsedCommand:
    """``name`` 不含斜杠；``raw_input`` 是名字后面的原文（含前导空白）。"""

    name: str
    raw_input: str


@dataclass(frozen=True)
class CommandSpec:
    name: str
    description: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Suggestion:
    """补全一项。``name`` 不含斜杠，是写回输入框的词。"""

    name: str
    description: str


@dataclass(frozen=True)
class CommandOutcome:
    kind: OutcomeKind
    text: str = ""
