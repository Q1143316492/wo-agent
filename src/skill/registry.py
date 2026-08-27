"""技能注册表：合并各 Provider 的目录，按名解析胜出项。

同名时先注册的 Provider 胜出（对应 dsh 的 rank/顺序，这里只用注册序）。
"""

from __future__ import annotations

import re

from .protocol import SKILL_NAME, SkillDefinition, SkillProvider, SkillSummary

_NAME = re.compile(SKILL_NAME)


def is_skill_name(name: str) -> bool:
    return bool(_NAME.fullmatch(name))


class SkillRegistry:
    """``ComposeContext.skills`` 的实现。"""

    def __init__(self) -> None:
        self._providers: list[SkillProvider] = []

    def add_provider(self, provider: SkillProvider) -> None:
        self._providers.append(provider)

    def list(self) -> list[SkillSummary]:
        seen: dict[str, SkillSummary] = {}
        for provider in self._providers:
            for summary in provider.list():
                if summary.name not in seen:
                    seen[summary.name] = summary
        return list(seen.values())

    def get(self, skill_name: str) -> SkillDefinition | None:
        if not is_skill_name(skill_name):
            return None
        for provider in self._providers:
            found = provider.get(skill_name)
            if found is not None:
                return found
        return None

    def catalog_text(self) -> str:
        """模型可见的目录投影。空目录返回空串，调用方不要写入会话。"""
        entries = self.list()
        if not entries:
            return ""
        lines = [
            "A skill is a reusable set of task-specific instructions. "
            "The following skills are available in this session:",
            "",
            "<available_skills>",
        ]
        for item in entries:
            desc = item.description.strip()
            if desc:
                lines.append(f"- `{item.name}`: {desc}")
            else:
                lines.append(f"- `{item.name}`")
        lines.extend(
            [
                "</available_skills>",
                "",
                "Load a skill with the `skill` tool by exact name before following its instructions. "
                "Do not load names that are not listed.",
            ]
        )
        return "\n".join(lines)
