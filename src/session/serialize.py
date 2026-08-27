"""会话事件及其嵌套值的无损 JSON 序列化。

dsh 的思想：持久化格式就是会话在内存中跑的那套类型化词汇——不造平行持久化
事件类型。序列化用 `dataclasses.asdict`（每个多态值已带 `type`/`kind` 判别
字段）；重建按判别字段分派，普通 dataclass（message、usage、finish、failure）
显式重建。
"""

from __future__ import annotations

from dataclasses import asdict

from llm.types import (
    BlockEnd,
    BlockStart,
    ContentBlock,
    FinishChunk,
    FinishReason,
    ImageBlock,
    LlmCallConfig,
    LLMMessage,
    LlmFailure,
    MessageSource,
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
    ToolSource,
    UsageChunk,
    UserSource,
)
from .events import (
    AssistantChunk,
    AssistantMessageEvent,
    CompactionEnd,
    CompactionStart,
    CompactionSummary,
    RequestHeaderEvent,
    SessionEventData,
    StepEnd,
    StepStart,
    SurfaceOp,
    SurfaceReplace,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)


def _source_from_dict(d: dict) -> MessageSource:
    kind = d.get("kind")
    if kind == "user":
        return UserSource()
    if kind == "model":
        return ModelSource(provider=d.get("provider", ""), model=d.get("model", ""))
    if kind == "tool":
        return ToolSource(call_id=d.get("call_id", ""))
    if kind == "plugin":
        return PluginSource(plugin=d.get("plugin", ""), compaction_id=d.get("compaction_id", ""))
    raise ValueError(f"unknown source kind: {kind!r}")


def _block_from_dict(d: dict) -> ContentBlock:
    t = d.get("type")
    if t == "text":
        return TextBlock(text=d.get("text", ""))
    if t == "reasoning":
        return ReasoningBlock(text=d.get("text", ""))
    if t == "image":
        return ImageBlock(url=d.get("url", ""))
    if t == "tool-call":
        return ToolCallBlock(
            id=d.get("id", ""), name=d.get("name", ""), arguments=d.get("arguments", "")
        )
    if t == "tool-result":
        return ToolResultBlock(
            tool_call_id=d.get("tool_call_id", ""),
            content=tuple(_block_from_dict(b) for b in d.get("content", [])),
            is_error=d.get("is_error", False),
        )
    raise ValueError(f"unknown block type: {t!r}")


def _usage_from_dict(d: dict) -> TokenUsage:
    return TokenUsage(
        input=d.get("input", 0),
        output=d.get("output", 0),
        cache_read=d.get("cache_read", 0),
        cache_write=d.get("cache_write", 0),
        reasoning=d.get("reasoning", 0),
    )


def _call_config_from_dict(d: dict) -> LlmCallConfig:
    return LlmCallConfig(
        provider=d.get("provider", ""),
        model=d.get("model", ""),
        max_tokens=d.get("max_tokens"),
        temperature=d.get("temperature"),
        reasoning_effort=d.get("reasoning_effort"),
        stop=tuple(d.get("stop", []) or []),
    )


def _failure_from_dict(d: dict) -> LlmFailure:
    return LlmFailure(
        message=d.get("message", ""),
        code=d.get("code", ""),
        status=d.get("status"),
        provider_retry_after_ms=d.get("provider_retry_after_ms"),
    )


def _finish_from_dict(d: dict) -> FinishReason:
    failure = _failure_from_dict(d["failure"]) if d.get("failure") else None
    return FinishReason(kind=d["kind"], failure=failure)


def _chunk_from_dict(d: dict) -> StreamChunk:
    t = d.get("type")
    if t == "block-start":
        return BlockStart(index=d["index"], block_type=d["block_type"])
    if t == "text-delta":
        return TextDelta(index=d["index"], text=d.get("text", ""))
    if t == "reasoning-delta":
        return ReasoningDelta(index=d["index"], text=d.get("text", ""))
    if t == "tool-call-delta":
        return ToolCallDelta(
            index=d["index"],
            id=d.get("id", ""),
            name=d.get("name"),
            arguments_delta=d.get("arguments_delta", ""),
        )
    if t == "block-end":
        return BlockEnd(index=d["index"], block=_block_from_dict(d["block"]))
    if t == "usage":
        return UsageChunk(usage=_usage_from_dict(d["usage"]))
    if t == "finish":
        return FinishChunk(reason=_finish_from_dict(d["reason"]))
    raise ValueError(f"unknown chunk type: {t!r}")


def _message_from_dict(d: dict) -> LLMMessage:
    return LLMMessage(
        id=d["id"],
        role=d["role"],
        content=tuple(_block_from_dict(b) for b in d.get("content", [])),
        source=_source_from_dict(d["source"]),
    )


def _surface_op_from_dict(value) -> SurfaceOp:
    if value is None or value == "append":
        return "append"
    if isinstance(value, dict) and value.get("op") == "replace":
        return SurfaceReplace(start=int(value["start"]), end=int(value["end"]))
    raise ValueError(f"unknown surface_op: {value!r}")


def event_to_dict(event: SessionEventData) -> dict:
    """Serialize one event (and everything nested) to a JSON-able dict."""
    return asdict(event)


def dict_to_event(d: dict) -> SessionEventData:
    """Reconstruct one event from its serialized dict."""
    t = d.get("type")
    if t == "turn/start":
        return TurnStart(turn=d["turn"])
    if t == "turn/end":
        return TurnEnd(turn=d["turn"], reason=d.get("reason", "completed"), error=d.get("error"))
    if t == "step/start":
        return StepStart(turn=d["turn"], step=d["step"])
    if t == "step/end":
        return StepEnd(turn=d["turn"], step=d["step"])
    if t == "user/message":
        return UserMessageEvent(
            message=_message_from_dict(d["message"]),
            surface_op=_surface_op_from_dict(d.get("surface_op", "append")),
            source_event_seqs=tuple(d.get("source_event_seqs") or ()),
        )
    if t == "assistant/chunk":
        return AssistantChunk(turn=d["turn"], step=d["step"], chunk=_chunk_from_dict(d["chunk"]))
    if t == "assistant/message":
        return AssistantMessageEvent(
            turn=d["turn"],
            step=d["step"],
            message=_message_from_dict(d["message"]),
            usage=_usage_from_dict(d["usage"]) if d.get("usage") else None,
            surface_op=_surface_op_from_dict(d.get("surface_op", "append")),
            source_event_seqs=tuple(d.get("source_event_seqs") or ()),
        )
    if t == "tool/call":
        return ToolCallEvent(
            turn=d["turn"], step=d["step"],
            call_id=d["call_id"], name=d["name"], arguments=d["arguments"],
        )
    if t == "tool/result":
        return ToolResultEvent(
            turn=d["turn"], step=d["step"],
            message=_message_from_dict(d["message"]), error=d.get("error"),
            surface_op=_surface_op_from_dict(d.get("surface_op", "append")),
            source_event_seqs=tuple(d.get("source_event_seqs") or ()),
        )
    if t == "request/header":
        return RequestHeaderEvent(
            header=_call_config_from_dict(d["header"]), reason=d.get("reason", "initial")
        )
    if t == "compaction/start":
        return CompactionStart(compaction_id=d["compaction_id"], turn=d.get("turn"))
    if t == "compaction/summary":
        return CompactionSummary(
            compaction_id=d["compaction_id"],
            summary=d.get("summary", ""),
            shadowed_start=d["shadowed_start"],
            shadowed_end=d["shadowed_end"],
            shadowed_seqs=tuple(d.get("shadowed_seqs") or ()),
            shadowed_chars=d.get("shadowed_chars", 0),
        )
    if t == "compaction/end":
        return CompactionEnd(
            compaction_id=d["compaction_id"],
            turn=d.get("turn"),
            error=d.get("error"),
        )
    raise ValueError(f"unknown event type: {t!r}")
