"""面向模型的 ``skill`` 工具（dsh ``tool-skill`` 消费方）。

只通过 SkillRegistry 取正文，不直接读盘。未知名 / 非法名变成 is_error 结果，
由循环写成持久的 tool/result。
"""

from __future__ import annotations

from llm.types import TextBlock
from tools import ToolDefinition

from .registry import SkillRegistry, is_skill_name


def make_skill_tool(registry: SkillRegistry) -> ToolDefinition:
    async def execute(args: dict) -> list:
        name = str(args.get("name") or "").strip()
        if not name:
            raise ValueError("skill name required")
        if not is_skill_name(name):
            raise ValueError(f"invalid skill name: {name}")
        found = registry.get(name)
        if found is None:
            raise ValueError(f"skill not found: {name}")
        return [TextBlock(text=found.content)]

    return ToolDefinition(
        name="skill",
        description=(
            "Load a skill by exact kebab-case name from the session catalog. "
            "Call this before following a skill's instructions. "
            "Do not load names that are not listed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Exact skill name from <available_skills>.",
                }
            },
            "required": ["name"],
        },
        execute=execute,
    )
