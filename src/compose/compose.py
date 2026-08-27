"""组合缝：把若干 Capability 挂到同一份运行时上下文。

对齐 dsh 的组合层思想，但不引入 Cordis / profile yaml。dsh 的原子单位是
插件的 ``apply(ctx)``；profile 只是按顺序列出要 apply 哪些插件。本模块的
``Capability.mount(ctx)`` 就是那次 apply；``compose()`` 就是幼体组装器。
以后把名单从代码换成配置，调用的仍是 ``compose(*caps)``。

循环（``ReactLoopAgent``）不出现在这里——它只消费组装结果里的
``ctx.tools`` / ``ctx.system_prompt`` / ``ctx.compaction``，不知道挂了哪些能力。
"""

from __future__ import annotations

from typing import Protocol

from skill.registry import SkillRegistry
from system_prompt import SystemPromptRegistry
from tools import RegistryToolExecutor


class ComposeContext:
    """一次组装的运行时上下文。

    ``tools`` / ``system_prompt`` / ``skills`` 永远在（dsh-base 里这三条也
    始终存在）。``compaction`` 默认 None：没挂 CompactionCapability 时循环
    不压缩。没挂对应 Capability 时注册表为空，循环看到空提示词、空工具。
    """

    def __init__(self) -> None:
        self.tools = RegistryToolExecutor()
        self.skills = SkillRegistry()
        self.system_prompt = SystemPromptRegistry()
        self.compaction = None


class Capability(Protocol):
    """一条可挂载能力。实现方自己往 ctx 上注册服务和工具。"""

    def mount(self, ctx: ComposeContext) -> None: ...


def compose(*capabilities: Capability) -> ComposeContext:
    """按参数顺序挂载能力，返回填好的上下文。"""
    ctx = ComposeContext()
    for cap in capabilities:
        cap.mount(ctx)
    return ctx
