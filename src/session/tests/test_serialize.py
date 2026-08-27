"""每个事件类型与嵌套值的无损 JSON 往返。"""

import json

from llm.types import (
    BlockEnd,
    BlockStart,
    FinishChunk,
    FinishReason,
    ImageBlock,
    LlmFailure,
    ModelSource,
    ReasoningBlock,
    ReasoningDelta,
    TextBlock,
    TextDelta,
    TokenUsage,
    ToolCallBlock,
    ToolCallDelta,
    ToolResultBlock,
    UsageChunk,
    create_model_message,
    create_tool_result_message,
    create_user_message,
)
from session.events import (
    AssistantChunk,
    AssistantMessageEvent,
    CompactionEnd,
    CompactionStart,
    CompactionSummary,
    RequestHeaderEvent,
    StepEnd,
    StepStart,
    SurfaceReplace,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from session.serialize import dict_to_event, event_to_dict


def _roundtrip(event):
    d = event_to_dict(event)
    # 必须能扛住真实的 JSON 编解码往返，而不只是 dict 往返
    restored = json.loads(json.dumps(d))
    rebuilt = dict_to_event(restored)
    assert rebuilt == event, f"round-trip mismatch for {event.type}"
    return rebuilt


def test_roundtrip_turn_boundaries():
    assert _roundtrip(TurnStart(turn=0)).turn == 0
    assert _roundtrip(TurnEnd(turn=0, reason="max-tokens")).reason == "max-tokens"
    assert _roundtrip(StepStart(turn=0, step=1)) == StepStart(turn=0, step=1)
    assert _roundtrip(StepEnd(turn=0, step=1)) == StepEnd(turn=0, step=1)


def test_roundtrip_user_message_with_all_block_types():
    user = UserMessageEvent(
        message=create_user_message([
            TextBlock(text="hi"),
            ImageBlock(url="data:image/png;base64,AAAA"),
        ])
    )
    rebuilt = _roundtrip(user)
    assert rebuilt.message.content == user.message.content
    assert isinstance(rebuilt.message.content[1], ImageBlock)


def test_roundtrip_assistant_message_with_usage_and_reasoning():
    assistant = AssistantMessageEvent(
        turn=0,
        step=0,
        message=create_model_message(
            [ReasoningBlock(text="think"), TextBlock(text="answer")],
            ModelSource(provider="deepseek", model="deepseek-chat"),
        ),
        usage=TokenUsage(input=10, output=5, cache_read=3, reasoning=4),
    )
    rebuilt = _roundtrip(assistant)
    assert rebuilt.message.content == assistant.message.content
    assert rebuilt.message.source == assistant.message.source
    assert rebuilt.usage == TokenUsage(input=10, output=5, cache_read=3, reasoning=4)


def test_roundtrip_assistant_chunk_all_shard_types():
    chunks = [
        BlockStart(index=0, block_type="text"),
        TextDelta(index=0, text="hi"),
        ReasoningDelta(index=0, text="think"),
        ToolCallDelta(index=1, id="c1", name="f", arguments_delta="{}"),
        BlockEnd(index=0, block=TextBlock(text="hi")),
        UsageChunk(usage=TokenUsage(input=1, output=1)),
        FinishChunk(reason=FinishReason(kind="stop")),
    ]
    for chunk in chunks:
        event = AssistantChunk(turn=0, step=0, chunk=chunk)
        rebuilt = _roundtrip(event)
        assert rebuilt.chunk == chunk, f"chunk round-trip failed: {chunk.type}"


def test_roundtrip_finish_with_error_failure():
    event = AssistantChunk(
        turn=0, step=0,
        chunk=FinishChunk(
            reason=FinishReason(
                kind="error",
                failure=LlmFailure(message="boom", code="AUTH", status=401),
            )
        ),
    )
    rebuilt = _roundtrip(event)
    assert rebuilt.chunk.reason.failure.code == "AUTH"
    assert rebuilt.chunk.reason.failure.status == 401


def test_roundtrip_tool_call_and_result():
    tc = ToolCallEvent(turn=0, step=0, call_id="c1", name="read", arguments='{"path":"/tmp/x"}')
    assert _roundtrip(tc) == tc

    tr = ToolResultEvent(
        turn=0, step=0,
        message=create_tool_result_message("c1", [TextBlock(text='{"ok": true}')], is_error=False),
    )
    rebuilt = _roundtrip(tr)
    assert rebuilt.message.content[0].type == "tool-result"
    assert rebuilt.message.source.call_id == "c1"


def test_roundtrip_tool_result_with_error_flag():
    tr = ToolResultEvent(
        turn=0, step=0,
        message=create_tool_result_message("c1", [TextBlock(text="failed")], is_error=True),
    )
    rebuilt = _roundtrip(tr)
    assert rebuilt.message.content[0].is_error is True


def test_roundtrip_request_header():
    from llm.types import LlmCallConfig

    ev = RequestHeaderEvent(
        header=LlmCallConfig(provider="deepseek", model="deepseek-chat", max_tokens=200,
                             temperature=0.5, reasoning_effort="medium", stop=("END",)),
        reason="initial",
    )
    rebuilt = _roundtrip(ev)
    assert rebuilt.header == ev.header
    assert rebuilt.reason == "initial"


def test_roundtrip_user_message_replace():
    from llm.types import PluginSource, create_message

    event = UserMessageEvent(
        message=create_message(
            "user",
            [TextBlock(text="SUM")],
            PluginSource(plugin="compact", compaction_id="cid1"),
        ),
        surface_op=SurfaceReplace(start=1, end=4),
        source_event_seqs=(0, 2, 1, 3, 4),
    )
    rebuilt = _roundtrip(event)
    assert rebuilt.surface_op == SurfaceReplace(start=1, end=4)
    assert rebuilt.source_event_seqs == (0, 2, 1, 3, 4)
    assert rebuilt.message.source.plugin == "compact"
    assert rebuilt.message.source.compaction_id == "cid1"


def test_roundtrip_compaction_lifecycle():
    start = CompactionStart(compaction_id="cid", turn=2)
    assert _roundtrip(start) == start
    summary = CompactionSummary(
        compaction_id="cid",
        summary="earlier work",
        shadowed_start=1,
        shadowed_end=4,
        shadowed_seqs=(1, 2, 4),
        shadowed_chars=120,
    )
    assert _roundtrip(summary) == summary
    end = CompactionEnd(compaction_id="cid", turn=2, error="boom")
    assert _roundtrip(end) == end
    idle = CompactionStart(compaction_id="cid", turn=None)
    assert _roundtrip(idle).turn is None
