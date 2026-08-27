"""wo-agent — 事件溯源会话层。

append-only 事件日志是 agent 交互的唯一事实源；模型可见历史由它派生。
分层铁律：本包只依赖 `llm.types`（共享词汇），不依赖其他。
"""

from .events import (
    AssistantChunk,
    AssistantMessageEvent,
    CompactionEnd,
    CompactionStart,
    CompactionSummary,
    SessionEventData,
    StepEnd,
    StepStart,
    SurfaceReplace,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
    is_surface_event,
)
from .session import Session, SessionEvent, derive_event_message, fold_surface
from .serialize import dict_to_event, event_to_dict
from .persistence import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionStore,
)
from .jsonl import JsonlSessionStore

__all__ = [
    "AssistantChunk",
    "AssistantMessageEvent",
    "CompactionEnd",
    "CompactionStart",
    "CompactionSummary",
    "JsonlSessionStore",
    "Session",
    "SessionCorruptionError",
    "SessionEvent",
    "SessionEventData",
    "SessionFormatUnsupportedError",
    "SessionStore",
    "StepEnd",
    "StepStart",
    "SurfaceReplace",
    "ToolCallEvent",
    "ToolResultEvent",
    "TurnEnd",
    "TurnStart",
    "UserMessageEvent",
    "derive_event_message",
    "dict_to_event",
    "event_to_dict",
    "fold_surface",
    "is_surface_event",
]
