"""默认命令表。未拿到 Booted.commands 时，测试和补全走这里。"""

from __future__ import annotations

from .builtins import mount_core
from .registry import CommandRegistry
from .types import CommandContext, CommandOutcome, ParsedCommand

TABLE = CommandRegistry()
mount_core(TABLE)


def help_text() -> str:
    return TABLE.help_text()


def dispatch(parsed: ParsedCommand, ctx: CommandContext | None = None) -> CommandOutcome:
    return TABLE.dispatch(parsed, ctx)
