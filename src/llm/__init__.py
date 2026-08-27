"""wo-agent — LLM 接入层。

`llm` 是栈底：provider 中立的词汇（types）、块组装器（assembler）、
上层依赖的 provider 缝（protocol）、薄注册表，以及 DeepSeek 适配器。

分层铁律：本包之上的代码只允许从 `llm.protocol` 和 `llm.types` import，
绝不 import `llm.deepseek`。
"""

from .types import (
    BlockEnd,
    BlockStart,
    ContentBlock,
    FinishChunk,
    FinishReason,
    ImageBlock,
    LLMMessage,
    LlmFailure,
    MessageSource,
    Model,
    ModelSource,
    PluginSource,
    ReasoningBlock,
    ReasoningDelta,
    StreamChunk,
    TextBlock,
    TextDelta,
    TokenUsage,
    ToolCallBlock,
    ToolCallDelta,
    ToolResultBlock,
    ToolSchema,
    ToolSource,
    UsageChunk,
    UserSource,
    create_message,
    create_model_message,
    create_system_message,
    create_tool_result_message,
    create_user_message,
)
from .protocol import LLMProvider, LLMRequest
from .registry import ModelRegistry
from .assembler import BlockAssembler
from .errors import LlmError, is_retryable
from .deepseek import DeepSeekConfig, DeepSeekProvider

__all__ = [
    "BlockAssembler",
    "BlockEnd",
    "BlockStart",
    "ContentBlock",
    "DeepSeekConfig",
    "DeepSeekProvider",
    "FinishChunk",
    "FinishReason",
    "ImageBlock",
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LlmError",
    "LlmFailure",
    "is_retryable",
    "MessageSource",
    "Model",
    "ModelRegistry",
    "ModelSource",
    "PluginSource",
    "ReasoningBlock",
    "ReasoningDelta",
    "StreamChunk",
    "TextBlock",
    "TextDelta",
    "TokenUsage",
    "ToolCallBlock",
    "ToolCallDelta",
    "ToolResultBlock",
    "ToolSchema",
    "ToolSource",
    "UsageChunk",
    "UserSource",
    "create_message",
    "create_model_message",
    "create_system_message",
    "create_tool_result_message",
    "create_user_message",
]
