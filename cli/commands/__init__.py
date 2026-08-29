"""斜杠命令：人发给 UI 的指令，不进模型、不进循环。

对齐 dsh ``packages/interaction/commands``：parse 与 handler 在注册表一侧；
画布只消费 ``CommandOutcome``。不把 ``/compact`` 做成产品命令。
"""

from .complete import apply_suggestion, suggest
from .dispatch import dispatch
from .parse import parse_line
from .types import CommandOutcome, CommandSpec, ParsedCommand, Suggestion

__all__ = [
    "CommandOutcome",
    "CommandSpec",
    "ParsedCommand",
    "Suggestion",
    "apply_suggestion",
    "dispatch",
    "parse_line",
    "suggest",
]

