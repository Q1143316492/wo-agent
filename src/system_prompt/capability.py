"""harness 身份段：挂到 ``ctx.system_prompt``，order = -100（对齐 dsh 约定）。"""

from __future__ import annotations

from .registry import PromptSection

DEFAULT_IDENTITY = (
    "You are wo-agent, a Python agent harness. "
    "Reply in Simplified Chinese unless the user writes in another language. "
    "Do not claim tools you do not have. "
    "Load a skill with the `skill` tool before following its instructions."
)


class SystemPromptCapability:
    """贡献固定身份段。persona 非空时再挂 order=0 的部署人格。"""

    def __init__(self, identity: str = DEFAULT_IDENTITY, persona: str = "") -> None:
        self._identity = identity
        self._persona = persona

    def mount(self, ctx) -> None:
        ctx.system_prompt.section(
            PromptSection(name="harness:identity", order=-100, text=self._identity)
        )
        if self._persona.strip():
            ctx.system_prompt.section(
                PromptSection(name="deployment:persona", order=0, text=self._persona)
            )
