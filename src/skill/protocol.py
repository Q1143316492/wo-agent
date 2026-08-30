"""skill 能力缝的接口定义（dsh ``ctx.skills`` / SkillProvider）。

注册表只合并目录、按名解析胜出项；技能正文从哪来由 Provider 决定。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

SKILL_NAME = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


@dataclass(frozen=True)
class SkillSummary:
    """目录项：给模型和系统提示词目录看的名字 + 短描述，不含正文。"""

    name: str
    description: str
    provider: str  # 来源名，如 "filesystem"


@dataclass(frozen=True)
class SkillDefinition:
    """一次 get() 的完整结果：目录元数据 + 正文。"""

    name: str
    description: str
    provider: str
    content: str


class SkillProvider(Protocol):
    """技能来源。文件系统、内存夹具、以后的远程源都实现它。"""

    name: str

    def list(self) -> list[SkillSummary]: ...
    def get(self, skill_name: str) -> SkillDefinition | None: ...
