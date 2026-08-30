"""Session.append 能写入的每一条事件。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from llm.types import LlmCallConfig, LLMMessage, StreamChunk, TokenUsage


@dataclass(frozen=True)
class SurfaceReplace:
    """按当前表层位置替换一段节点。``start`` / ``end`` 是表层节点的 seq，
    不是盲目的数值区间——先前的 replace 可能已打乱 seq 与表层顺序的对应。
    """

    start: int
    end: int
    op: Literal["replace"] = "replace"


SurfaceOp = Union[Literal["append"], SurfaceReplace]


@dataclass(frozen=True)
class TurnStart:
    turn: int
    type: Literal["turn/start"] = "turn/start"


@dataclass(frozen=True)
class TurnEnd:
    turn: int
    reason: str = "completed"  # 可选：completed | aborted | error | max-tokens | ...
    error: str | None = None
    type: Literal["turn/end"] = "turn/end"


@dataclass(frozen=True)
class StepStart:
    turn: int
    step: int
    type: Literal["step/start"] = "step/start"


@dataclass(frozen=True)
class StepEnd:
    turn: int
    step: int
    type: Literal["step/end"] = "step/end"


@dataclass(frozen=True)
class UserMessageEvent:
    """一条出现在模型可见 surface 上的 user 角色消息（普通提示词或注入的上下文）。"""

    message: LLMMessage
    surface_op: SurfaceOp = "append"
    source_event_seqs: tuple[int, ...] = ()
    type: Literal["user/message"] = "user/message"


@dataclass(frozen=True)
class AssistantChunk:
    """一条原始流分片——token 级重放保真。"""
    turn: int
    step: int
    chunk: StreamChunk
    type: Literal["assistant/chunk"] = "assistant/chunk"


@dataclass(frozen=True)
class AssistantMessageEvent:
    """一步的组装后 assistant 消息（派生历史用它）。"""
    turn: int
    step: int
    message: LLMMessage
    usage: TokenUsage | None = None
    surface_op: SurfaceOp = "append"
    source_event_seqs: tuple[int, ...] = ()
    type: Literal["assistant/message"] = "assistant/message"


@dataclass(frozen=True)
class ToolCallEvent:
    """模型请求了一次工具调用。"""
    turn: int
    step: int
    call_id: str
    name: str
    arguments: str  # 模型产出的原始 JSON 字符串
    type: Literal["tool/call"] = "tool/call"


@dataclass(frozen=True)
class ToolResultEvent:
    """一次已完成的工具调用的模型可见结果。"""
    turn: int
    step: int
    message: LLMMessage  # user 角色消息，携带 tool-result 块
    error: str | None = None
    surface_op: SurfaceOp = "append"
    source_event_seqs: tuple[int, ...] = ()
    type: Literal["tool/result"] = "tool/result"


@dataclass(frozen=True)
class RequestHeaderEvent:
    """一次请求的完整调用配置，作为会话状态记录。

    补全"模型可见 = 必须落日志"：derive_messages 还原对话内容，本事件还原
    每次调用所用的配置。``reason`` 是 ``initial`` / ``resume`` / ``change``
    （dsh request/header）。
    """

    header: LlmCallConfig
    reason: str = "initial"
    type: Literal["request/header"] = "request/header"


@dataclass(frozen=True)
class CompactionStart:
    """压缩事务开锁。仅日志，不上表层。"""

    compaction_id: str
    turn: int | None = None
    type: Literal["compaction/start"] = "compaction/start"


@dataclass(frozen=True)
class CompactionSummary:
    """压缩事务的摘要记录。仅日志；表层变更是随后那条 replace 的 user/message。"""

    compaction_id: str
    summary: str
    shadowed_start: int
    shadowed_end: int
    shadowed_seqs: tuple[int, ...] = ()
    shadowed_chars: int = 0
    type: Literal["compaction/summary"] = "compaction/summary"


@dataclass(frozen=True)
class CompactionEnd:
    """压缩事务闭锁。``error`` 非空表示本次未提交表层替换。"""

    compaction_id: str
    turn: int | None = None
    error: str | None = None
    type: Literal["compaction/end"] = "compaction/end"


SessionEventData = Union[
    TurnStart,
    TurnEnd,
    StepStart,
    StepEnd,
    UserMessageEvent,
    AssistantChunk,
    AssistantMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    RequestHeaderEvent,
    CompactionStart,
    CompactionSummary,
    CompactionEnd,
]

#: 会产生模型消息的事件类型 —— surface。
SurfaceEventType = Literal["user/message", "assistant/message", "tool/result"]
SURFACE_TYPES: frozenset[str] = frozenset({"user/message", "assistant/message", "tool/result"})


def is_surface_event(event: SessionEventData) -> bool:
    return event.type in SURFACE_TYPES
