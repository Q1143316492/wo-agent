"""wo-agent — 系统提示词组装。"""

from .agents_md import AgentsMdCapability
from .capability import DEFAULT_IDENTITY, SystemPromptCapability
from .registry import PromptSection, SystemPromptRegistry

__all__ = [
    "AgentsMdCapability",
    "DEFAULT_IDENTITY",
    "PromptSection",
    "SystemPromptCapability",
    "SystemPromptRegistry",
]
