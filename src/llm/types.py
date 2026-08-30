"""Provider 中立的 LLM 词汇。

吸收自 pi-ai 与 deepseek-harness 的设计（不照搬其类划分）：

- 内容块是类型化联合；工具调用本身就是一种内容块（消息上不再有独立
  `tool_calls` 字段）。
- 消息是不可变值，带稳定 `id` 与类型化 `source`（谁产生的）。用 `create_*`
  工厂构造消息，把 role/source 的不变量收在工厂里。
- 流是分片协议：`block-start` / `*-delta` / `block-end` / `usage` / `finish`。
  `finish` 是唯一终止；错误或中止也是 `finish`，其 reason 携带结构化失败。
- token 计数是 DISJOINT：`input` 不含缓存；缓存读写是独立字段。DeepSeek 的
  `prompt_tokens` 包含缓存命中，适配器要减掉。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal, Union

Role = Literal["system", "user", "assistant"]


# ---- 内容块 ----

@dataclass(frozen=True)
class TextBlock:
    type: Literal["text"] = "text"
    text: str = ""


@dataclass(frozen=True)
class ReasoningBlock:
    type: Literal["reasoning"] = "reasoning"
    text: str = ""


@dataclass(frozen=True)
class ImageBlock:
    type: Literal["image"] = "image"
    url: str = ""


@dataclass(frozen=True)
class ToolCallBlock:
    type: Literal["tool-call"] = "tool-call"
    id: str = ""
    name: str = ""
    arguments: str = ""  # 模型产出的原始 JSON 字符串


@dataclass(frozen=True)
class ToolResultBlock:
    type: Literal["tool-result"] = "tool-result"
    tool_call_id: str = ""
    content: tuple[ContentBlock, ...] = ()
    is_error: bool = False


ContentBlock = Union[TextBlock, ReasoningBlock, ImageBlock, ToolCallBlock, ToolResultBlock]


# ---- 消息来源（谁产生了这条消息）----

@dataclass(frozen=True)
class UserSource:
    kind: Literal["user"] = "user"


@dataclass(frozen=True)
class ModelSource:
    kind: Literal["model"] = "model"
    provider: str = ""
    model: str = ""


@dataclass(frozen=True)
class ToolSource:
    kind: Literal["tool"] = "tool"
    call_id: str = ""


@dataclass(frozen=True)
class PluginSource:
    """插件产生的消息。``plugin='compact'`` 时 ``compaction_id`` 把检查点
    关联到对应的 ``compaction/*`` 事务（对齐 dsh ``compactCheckpointSource``）。
    """

    kind: Literal["plugin"] = "plugin"
    plugin: str = ""
    compaction_id: str = ""


MessageSource = Union[UserSource, ModelSource, ToolSource, PluginSource]


# ---- 消息值 ----

@dataclass(frozen=True)
class LLMMessage:
    id: str
    role: Role
    content: tuple[ContentBlock, ...]
    source: MessageSource


def create_message(
    role: Role,
    content: list[ContentBlock] | tuple[ContentBlock, ...],
    source: MessageSource,
    message_id: str | None = None,
) -> LLMMessage:
    """构造一条冻结消息；未提供 id 时铸造一个稳定 id。"""
    return LLMMessage(
        id=message_id or uuid.uuid4().hex,
        role=role,
        content=tuple(content),
        source=source,
    )


def create_user_message(content: list[ContentBlock] | tuple[ContentBlock, ...]) -> LLMMessage:
    return create_message("user", content, UserSource())


def create_system_message(text: str) -> LLMMessage:
    return create_message("system", [TextBlock(text=text)], UserSource())


def create_model_message(
    content: list[ContentBlock] | tuple[ContentBlock, ...],
    source: ModelSource,
) -> LLMMessage:
    return create_message("assistant", content, source)


def create_tool_result_message(
    tool_call_id: str,
    content: list[ContentBlock] | tuple[ContentBlock, ...],
    is_error: bool = False,
) -> LLMMessage:
    return create_message(
        "user",
        [ToolResultBlock(tool_call_id=tool_call_id, content=tuple(content), is_error=is_error)],
        ToolSource(call_id=tool_call_id),
    )


# ---- 模型描述（能力元数据；仅供参考，不是请求旋钮）----

@dataclass(frozen=True)
class Model:
    id: str
    provider: str
    base_url: str = ""
    reasoning: bool = False
    input_modalities: tuple[str, ...] = ("text",)
    context_window: int = 0
    max_tokens: int = 0


@dataclass(frozen=True)
class LlmCallConfig:
    """单次调用的配置，作为会话状态记录（request/header）。

    出自 dsh call-config 的思想：配置是会话级事实——记下来，重放就能还原
    当时到底发了什么。``reasoning_effort`` 与 ``stop`` 先进入词汇；适配器
    各自映射它们支持的部分。
    """

    provider: str
    model: str
    max_tokens: int | None = None
    temperature: float | None = None
    reasoning_effort: str | None = None
    stop: tuple[str, ...] = ()


# ---- 失败、用量、终止 ----

@dataclass(frozen=True)
class TokenUsage:
    input: int = 0  # 仅未缓存的输入 token
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    reasoning: int = 0


@dataclass(frozen=True)
class LlmFailure:
    message: str
    code: str
    status: int | None = None
    provider_retry_after_ms: int | None = None


@dataclass(frozen=True)
class FinishReason:
    kind: Literal["stop", "tool-calls", "max-tokens", "aborted", "error"]
    failure: LlmFailure | None = None


# ---- 流分片（适配器发出的 wire 协议）----

@dataclass(frozen=True)
class BlockStart:
    index: int
    block_type: str
    type: Literal["block-start"] = "block-start"


@dataclass(frozen=True)
class TextDelta:
    """回答文本的一小段增量。例如模型吐出 "2"，就是 TextDelta(text="2")。"""

    index: int
    text: str
    type: Literal["text-delta"] = "text-delta"


@dataclass(frozen=True)
class ReasoningDelta:
    index: int
    text: str
    type: Literal["reasoning-delta"] = "reasoning-delta"


@dataclass(frozen=True)
class ToolCallDelta:
    index: int
    id: str = ""
    name: str | None = None
    arguments_delta: str = ""
    type: Literal["tool-call-delta"] = "tool-call-delta"


@dataclass(frozen=True)
class BlockEnd:
    block: ContentBlock
    index: int = 0
    type: Literal["block-end"] = "block-end"


@dataclass(frozen=True)
class UsageChunk:
    usage: TokenUsage
    type: Literal["usage"] = "usage"


@dataclass(frozen=True)
class FinishChunk:
    reason: FinishReason
    type: Literal["finish"] = "finish"


StreamChunk = Union[
    BlockStart,
    TextDelta,
    ReasoningDelta,
    ToolCallDelta,
    BlockEnd,
    UsageChunk,
    FinishChunk,
]


@dataclass(frozen=True)
class ToolSchema:
    """面向模型的工具声明：模型靠它知道有哪些工具、怎么调用。

    声明在 llm（而非 tools 包），因为它是请求（GenerateOptions.tools）的一
    部分；带执行实现的 `ToolDefinition` 在 tools 包。
    """

    name: str
    description: str
    parameters: dict  # JSON Schema
