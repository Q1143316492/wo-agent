"""内置命令目录与分发。TUI 不写 if text == '/quit'。"""

from __future__ import annotations

from .types import CommandOutcome, CommandSpec, ParsedCommand

COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("help", "列出命令"),
    CommandSpec("clear", "清空屏幕（不删会话日志）"),
    CommandSpec("quit", "退出"),
)

_ALIASES: dict[str, str] = {}
for _spec in COMMANDS:
    _ALIASES[_spec.name] = _spec.name
    for _alias in _spec.aliases:
        _ALIASES[_alias] = _spec.name


def help_text() -> str:
    lines = ["命令："]
    for spec in COMMANDS:
        names = ", ".join(f"/{n}" for n in (spec.name, *spec.aliases))
        lines.append(f"  {names}  {spec.description}")
    return "\n".join(lines)


def dispatch(parsed: ParsedCommand) -> CommandOutcome:
    canonical = _ALIASES.get(parsed.name)
    if canonical is None:
        return CommandOutcome("unknown", f"未知命令 /{parsed.name}。输入 /help 查看。")
    if canonical == "quit":
        return CommandOutcome("quit")
    if canonical == "clear":
        return CommandOutcome("clear")
    return CommandOutcome("help", help_text())
