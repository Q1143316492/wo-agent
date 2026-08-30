"""斜杠命令表：登记、补全、分发。TUI 和 Capability.mount 都往这里写。"""

from __future__ import annotations

from .types import CommandContext, CommandOutcome, CommandSpec, ParsedCommand, Suggestion


class CommandRegistry:
    def __init__(self) -> None:
        self._specs: list[CommandSpec] = []
        self._by_name: dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        names = (spec.name, *spec.aliases)
        for name in names:
            if name in self._by_name:
                raise ValueError(f"duplicate command: {name}")
        self._specs.append(spec)
        for name in names:
            self._by_name[name] = spec

    def specs(self) -> tuple[CommandSpec, ...]:
        return tuple(self._specs)

    def help_text(self) -> str:
        lines = ["命令："]
        for spec in self._specs:
            names = ", ".join(f"/{n}" for n in (spec.name, *spec.aliases))
            lines.append(f"  {names}  {spec.description}")
        return "\n".join(lines)

    def suggest(self, typed: str) -> tuple[Suggestion, ...]:
        if not typed.startswith("/") or any(ch in typed for ch in " \t\n\r"):
            return ()
        needle = typed[1:].lower()
        out: list[Suggestion] = []
        for spec in self._specs:
            for name in (spec.name, *spec.aliases):
                if name.startswith(needle):
                    out.append(Suggestion(name=name, description=spec.description))
        return tuple(out)

    def dispatch(self, parsed: ParsedCommand, ctx: CommandContext | None = None) -> CommandOutcome:
        spec = self._by_name.get(parsed.name)
        if spec is None or spec.handler is None:
            return CommandOutcome("unknown", f"未知命令 /{parsed.name}。输入 /help 查看。")
        return spec.handler(parsed, ctx if ctx is not None else CommandContext())
