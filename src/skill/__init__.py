"""wo-agent — skill 能力缝。

三方：``protocol`` / ``registry``（接口）、``filesystem``（实现）、``tool``（消费）。
``SkillCapability`` 把实现和消费一次 mount 进组合上下文。
"""

from .capability import SkillCapability
from .filesystem import FilesystemSkillProvider
from .protocol import SkillDefinition, SkillProvider, SkillSummary
from .registry import SkillRegistry, is_skill_name
from .tool import make_skill_tool

__all__ = [
    "FilesystemSkillProvider",
    "SkillCapability",
    "SkillDefinition",
    "SkillProvider",
    "SkillRegistry",
    "SkillSummary",
    "is_skill_name",
    "make_skill_tool",
]
