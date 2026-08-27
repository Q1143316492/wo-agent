"""系统提示词组装（dsh ``ctx.systemPrompt`` 的段注册表）。

插件贡献有序段；循环在每一步 ``assemble()``，把结果作为请求的第一条
system 消息。系统提示词来自活的注册表，不进 session 日志——和 dsh 一样，
前缀由当前组装重建。动态上下文（skill 目录热更新进 user 消息）以后再加。

不做：``{{var}}`` 插值、complete 段、toolOrder、waterfall、scope。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

PromptText = str | Callable[[], str]


@dataclass(frozen=True)
class PromptSection:
    """一段系统提示词。``order`` 升序拼接；同 order 按注册序。"""

    name: str
    order: int
    text: PromptText


class SystemPromptRegistry:
    def __init__(self) -> None:
        self._sections: list[PromptSection] = []

    def section(self, section: PromptSection) -> None:
        if any(existing.name == section.name for existing in self._sections):
            raise ValueError(f"duplicate prompt section: {section.name}")
        self._sections.append(section)

    def assemble(self) -> str:
        """求值、丢掉空段、按 order 用空行拼接。"""
        ranked = sorted(enumerate(self._sections), key=lambda item: (item[1].order, item[0]))
        parts: list[str] = []
        for _, section in ranked:
            raw = section.text() if callable(section.text) else section.text
            text = raw.strip()
            if text:
                parts.append(text)
        return "\n\n".join(parts)
