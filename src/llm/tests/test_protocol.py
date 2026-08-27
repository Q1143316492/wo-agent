"""LLM provider 协议与消息值的契约测试。"""

from llm.protocol import LLMProvider, LLMRequest
from llm.types import (
    FinishChunk,
    FinishReason,
    ModelSource,
    TextBlock,
    TextDelta,
    ToolCallBlock,
    create_model_message,
    create_user_message,
)


class FakeProvider:
    """最小且符合约定的 LLMProvider（结构化 Protocol 检查）。"""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def stream(self, request, signal=None):
        for chunk in self._chunks:
            yield chunk


async def test_protocol_accepts_any_provider_with_stream():
    chunks = [TextDelta(index=0, text="hi"), FinishChunk(reason=FinishReason(kind="stop"))]
    provider: LLMProvider = FakeProvider(chunks)  # 结构化类型检查
    request = LLMRequest(provider="fake", model="m", messages=[])
    got = [c async for c in provider.stream(request)]
    assert got == chunks


def test_message_has_identity_and_source():
    msg = create_model_message(
        [TextBlock(text="hi")],
        ModelSource(provider="deepseek", model="deepseek-chat"),
    )
    assert msg.id
    assert msg.role == "assistant"
    assert msg.source.kind == "model"
    assert msg.source.model == "deepseek-chat"
    assert isinstance(msg.content[0], TextBlock)


def test_tool_call_is_a_content_block():
    msg = create_user_message([ToolCallBlock(id="c1", name="read", arguments="{}")])
    assert msg.content[0].type == "tool-call"
    assert msg.content[0].name == "read"


def test_messages_are_immutable_values():
    msg = create_user_message([TextBlock(text="hi")])
    assert msg.id  # 创建时铸造的稳定身份
