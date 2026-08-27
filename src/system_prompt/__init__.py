"""wo-agent — 系统提示词组装。"""

from .capability import DEFAULT_IDENTITY, SystemPromptCapability
from .registry import PromptSection, SystemPromptRegistry

__all__ = [
    "DEFAULT_IDENTITY",
    "PromptSection",
    "SystemPromptCapability",
    "SystemPromptRegistry",
]
