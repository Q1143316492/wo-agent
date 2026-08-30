"""从工作区往上找 AGENTS.md / CLAUDE.md，挂进系统提示词。"""

from __future__ import annotations

from pathlib import Path

from .registry import PromptSection

_NAMES = ("AGENTS.md", "CLAUDE.md")


class AgentsMdCapability:
    def __init__(self, root: str | Path, stop_at: str | Path | None = None) -> None:
        self._root = Path(root)
        self._stop_at = Path(stop_at) if stop_at is not None else Path.home()

    def mount(self, ctx) -> None:
        for order, directory in enumerate(self._directories(), start=50):
            for name in _NAMES:
                path = directory / name
                text = _read(path)
                if not text:
                    continue
                ctx.system_prompt.section(
                    PromptSection(name=f"agents-md:{path.resolve()}", order=order, text=text)
                )

    def _directories(self) -> list[Path]:
        root = self._root.resolve()
        stop_at = self._stop_at.resolve()
        found: list[Path] = []
        current = root
        while True:
            found.append(current)
            if current == stop_at or current.parent == current:
                break
            current = current.parent
        found.reverse()
        return found


def _read(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
