"""wo-agent — 组合层。

按 Capability 组装一次运行：循环不参与选择，只消费组装结果。
"""

from .assemble import Assembled, assemble
from .compose import Capability, ComposeContext, compose

__all__ = ["Assembled", "Capability", "ComposeContext", "assemble", "compose"]
