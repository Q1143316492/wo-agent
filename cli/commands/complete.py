"""斜杠补全：只根据目录过滤，不碰 Textual。

对齐 pi ``CombinedAutocompleteProvider`` 的命令分支：行首 ``/``、尚未输入空格时出名字。
参数补全以后再加。
"""

from __future__ import annotations

from .dispatch import COMMANDS
from .types import Suggestion


def suggest(typed: str) -> tuple[Suggestion, ...]:
    """``typed`` 是输入框全文。不是斜杠名字补全则返回空。"""
    if not typed.startswith("/") or any(ch in typed for ch in " \t\n\r"):
        return ()
    needle = typed[1:].lower()
    out: list[Suggestion] = []
    for spec in COMMANDS:
        for name in (spec.name, *spec.aliases):
            if name.startswith(needle):
                out.append(Suggestion(name=name, description=spec.description))
    return tuple(out)


def apply_suggestion(name: str) -> str:
    """写入输入框的文本。末尾空格留给以后的参数。"""
    return f"/{name} "
