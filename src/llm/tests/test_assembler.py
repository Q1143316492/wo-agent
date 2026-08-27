"""BlockAssembler 测试：分片 -> 内容块 -> assistant 消息。"""

from llm.assembler import BlockAssembler
from llm.types import (
    BlockEnd,
    BlockStart,
    FinishChunk,
    FinishReason,
    ModelSource,
    ReasoningBlock,
    ReasoningDelta,
    TextBlock,
    TextDelta,
    TokenUsage,
    ToolCallBlock,
    ToolCallDelta,
    UsageChunk,
)


def test_assembles_text_block():
    a = BlockAssembler()
    a.push(BlockStart(index=0, block_type="text"))
    a.push(TextDelta(index=0, text="Hel"))
    a.push(TextDelta(index=0, text="lo"))
    a.push(BlockEnd(index=0, block=TextBlock(text="Hello")))
    a.push(FinishChunk(reason=FinishReason(kind="stop")))
    assert a.blocks() == [TextBlock(text="Hello")]
    assert a.finish.kind == "stop"


def test_assembles_open_block_from_deltas_without_block_end():
    # 纯 delta 协议（无 block-start/end）：从累积的 delta 组装
    a = BlockAssembler()
    a.push(TextDelta(index=0, text="hi"))
    assert a.blocks() == [TextBlock(text="hi")]


def test_block_end_wins_over_straggler_deltas():
    a = BlockAssembler()
    a.push(BlockStart(index=0, block_type="text"))
    a.push(TextDelta(index=0, text="partial"))
    a.push(BlockEnd(index=0, block=TextBlock(text="canonical")))
    a.push(TextDelta(index=0, text="straggler"))  # 忽略：块已关闭
    assert a.blocks() == [TextBlock(text="canonical")]


def test_tool_call_assembly_with_id_and_name():
    a = BlockAssembler()
    a.push(ToolCallDelta(index=0, id="call_1", name="read_file", arguments_delta='{"path"'))
    a.push(ToolCallDelta(index=0, arguments_delta=':"/tmp/x"}'))
    a.push(FinishChunk(reason=FinishReason(kind="tool-calls")))
    assert a.blocks() == [
        ToolCallBlock(id="call_1", name="read_file", arguments='{"path":"/tmp/x"}')
    ]
    assert a.finish.kind == "tool-calls"


def test_reasoning_and_text_blocks_in_stream_order():
    a = BlockAssembler()
    a.push(ReasoningDelta(index=0, text="think"))
    a.push(TextDelta(index=1, text="answer"))
    assert a.blocks() == [ReasoningBlock(text="think"), TextBlock(text="answer")]


def test_usage_and_message():
    a = BlockAssembler()
    a.push(TextDelta(index=0, text="hi"))
    a.push(UsageChunk(usage=TokenUsage(input=1, output=2)))
    a.push(FinishChunk(reason=FinishReason(kind="stop")))
    assert a.usage == TokenUsage(input=1, output=2)
    msg = a.message(source=ModelSource(provider="p", model="m"))
    assert msg.role == "assistant"
    assert msg.content == (TextBlock(text="hi"),)
    assert msg.source.kind == "model"


def test_max_tokens_drops_tool_calls():
    a = BlockAssembler()
    a.push(ToolCallDelta(index=0, id="c1", name="f", arguments_delta="{}"))
    a.push(TextDelta(index=1, text="partial"))
    a.push(FinishChunk(reason=FinishReason(kind="max-tokens")))
    assert [b.type for b in a.blocks()] == ["text"]  # 不安全的工具调用被丢弃


def test_default_finish_is_stop():
    a = BlockAssembler()
    assert a.finish.kind == "stop"
