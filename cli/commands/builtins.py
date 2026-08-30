"""产品自带的斜杠命令。Capability.mount 时往表里登记。"""

from __future__ import annotations

from .registry import CommandRegistry
from .types import CommandContext, CommandOutcome, CommandSpec, ParsedCommand


def mount_core(table: CommandRegistry) -> None:
    def help_cmd(_parsed: ParsedCommand, _ctx: CommandContext) -> CommandOutcome:
        return CommandOutcome("help", table.help_text())

    def clear_cmd(_parsed: ParsedCommand, _ctx: CommandContext) -> CommandOutcome:
        return CommandOutcome("clear")

    def quit_cmd(_parsed: ParsedCommand, _ctx: CommandContext) -> CommandOutcome:
        return CommandOutcome("quit")

    table.register(CommandSpec("help", "列出命令", handler=help_cmd))
    table.register(CommandSpec("clear", "清空屏幕（不删会话日志）", handler=clear_cmd))
    table.register(CommandSpec("quit", "退出", handler=quit_cmd))


def mount_session(table: CommandRegistry) -> None:
    table.register(CommandSpec("resume", "列出或续上一次会话", handler=_resume))
    table.register(CommandSpec("new", "新开会话", handler=_new))
    table.register(CommandSpec("name", "给当前会话起名", handler=_name))


def _resume(parsed: ParsedCommand, ctx: CommandContext) -> CommandOutcome:
    store = ctx.store
    if store is None:
        return CommandOutcome("note", "没有会话存储。")
    needle = parsed.raw_input.strip()
    ids = store.list()
    if not needle:
        if not ids:
            return CommandOutcome("note", "还没有会话。")
        lines = ["会话（新→旧）："]
        for sid in ids:
            loaded = store.load(sid)
            title = loaded.title if loaded is not None and loaded.title else "未命名"
            lines.append(f"  {sid[:8]}  {title}")
        lines.append("输入 /resume <id> 续上。")
        return CommandOutcome("note", "\n".join(lines))
    matches = [sid for sid in ids if sid.startswith(needle)]
    if len(matches) == 1:
        return CommandOutcome("load_session", session_id=matches[0])
    if not matches:
        return CommandOutcome("note", f"没有以 {needle} 开头的会话。")
    shown = ", ".join(sid[:8] for sid in matches)
    return CommandOutcome("note", f"匹配到多条：{shown}。再写长一点。")


def _new(parsed: ParsedCommand, ctx: CommandContext) -> CommandOutcome:
    session = ctx.session
    store = ctx.store
    if store is not None and session is not None and (session.events or session.title):
        store.save(session)
    return CommandOutcome("new_session")


def _name(parsed: ParsedCommand, ctx: CommandContext) -> CommandOutcome:
    title = parsed.raw_input.strip()
    if not title:
        return CommandOutcome("note", "用法：/name 标题")
    session = ctx.session
    if session is None:
        return CommandOutcome("note", "没有当前会话。")
    session.title = title
    if ctx.store is not None:
        ctx.store.save(session)
    return CommandOutcome("note", f"已命名为 {title}")
