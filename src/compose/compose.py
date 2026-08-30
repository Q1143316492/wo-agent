"""组合：把若干 Capability 挂到同一份运行时上下文。

对齐 dsh 的组合层思想，但不引入 Cordis / profile yaml。dsh 的原子单位是
插件的 ``apply(ctx)``；profile 只是按顺序列出要 apply 哪些插件。本模块的
``Capability.mount(ctx)`` 就是那次 apply；``compose()`` 按名单调用 mount。

循环（``ReactLoopAgent``）不出现在这里——它只消费 ``ctx.tools`` /
``ctx.system_prompt`` / ``ctx.compaction``。session 与循环由宿主构造。
"""

from __future__ import annotations

from typing import Protocol

from skill.registry import SkillRegistry
from system_prompt import SystemPromptRegistry
from tools import RegistryToolExecutor


class ComposeContext:
    """一次组装的运行时上下文。

    ``tools`` / ``system_prompt`` / ``skills`` 永远在。``compaction`` 默认
    None。``commands`` 由宿主传入，本包不认识斜杠命令的类型。
    """

    def __init__(self) -> None:
        self.tools = RegistryToolExecutor()
        self.skills = SkillRegistry()
        self.system_prompt = SystemPromptRegistry()
        self.compaction = None
        self.commands = None


class Capability(Protocol):
    """一条可挂载能力。实现方自己往 ctx 上注册服务和工具。"""

    def mount(self, ctx: ComposeContext) -> None: ...


def compose(*capabilities: Capability, commands=None) -> ComposeContext:
    """按参数顺序挂载能力，返回填好的上下文。"""
    ctx = ComposeContext()
    ctx.commands = commands
    for cap in capabilities:
        cap.mount(ctx)
    return ctx
