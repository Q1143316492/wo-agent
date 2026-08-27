"""skill 能力：往组合上下文挂 Provider + 面向模型的 ``skill`` 工具。

这是 dsh 里 ``skill-filesystem`` + ``tool-skill`` 两个插件在 Python 里的一次
mount。循环不知道 skill；没把本 Capability 传进 ``compose()`` 的组装就没有
skill 工具，也没有目录。
"""

from __future__ import annotations

from pathlib import Path

from system_prompt import PromptSection

from .filesystem import FilesystemSkillProvider
from .tool import make_skill_tool


class SkillCapability:
    def __init__(self, *directories: str | Path) -> None:
        self._directories = tuple(Path(d) for d in directories)

    def mount(self, ctx) -> None:
        for directory in self._directories:
            ctx.skills.add_provider(FilesystemSkillProvider(directory))
        ctx.tools.register(make_skill_tool(ctx.skills))
        # 目录进系统提示词（每步 assemble），不再 seed 成 user 消息
        ctx.system_prompt.section(
            PromptSection(name="skill:catalog", order=100, text=lambda: ctx.skills.catalog_text())
        )
