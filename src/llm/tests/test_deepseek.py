"""DeepSeek 适配器对固定 SSE 响应的测试——无网络、无 key。"""

import asyncio
import json

import httpx

from llm.assembler import BlockAssembler
from llm.deepseek import DeepSeekConfig, DeepSeekProvider
from llm.protocol import LLMRequest
from llm.types import (
    FinishChunk,
    ImageBlock,
    ModelSource,
    ReasoningBlock,
    TextBlock,
    TokenUsage,
    ToolCallBlock,
    create_message,
    create_system_message,
    create_tool_result_message,
    create_user_message,
)


def _sse(events):
    """把事件（dict）序列化成以 [DONE] 结尾的 SSE body。"""
    lines = []
    for event in events:
        lines.append(f"data: {json.dumps(event, ensure_ascii=False)}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode("utf-8")


def _provider(stream_bytes, handler_hook=None):
    def handler(request):
        if handler_hook:
            handler_hook(request)
        return httpx.Response(200, content=stream_bytes, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DeepSeekProvider(DeepSeekConfig(api_key="test-key"), client=client)
    return provider, client


def _request():
    return LLMRequest(
        provider="deepseek",
        model="deepseek-chat",
        messages=[create_user_message([TextBlock(text="hi")])],
    )


async def _collect(provider, request):
    return [c async for c in provider.stream(request)]


def _assemble(chunks):
    a = BlockAssembler()
    for c in chunks:
        a.push(c)
    return a


async def test_text_stream_shards_and_assembly():
    events = [
        {"choices": [{"delta": {"role": "assistant", "content": "Hello"}, "index": 0, "finish_reason": None}]},
        {"choices": [{"delta": {"content": " world"}, "index": 0, "finish_reason": None}]},
        {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
    ]
    provider, client = _provider(_sse(events))
    try:
        got = await _collect(provider, _request())

        # 分片序列：block-start、text-delta x2、block-end、usage、finish
        assert [c.type for c in got] == ["block-start", "text-delta", "text-delta", "block-end", "usage", "finish"]

        a = _assemble(got)
        assert a.blocks() == [TextBlock(text="Hello world")]
        assert a.usage == TokenUsage(input=10, output=5, cache_read=0)
        assert a.finish.kind == "stop"
    finally:
        await client.aclose()


async def test_reasoning_and_tool_call_shards():
    events = [
        {"choices": [{"delta": {"reasoning_content": "think..."}, "index": 0, "finish_reason": None}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                                 "function": {"name": "read_file", "arguments": ""}}]},
                      "index": 0, "finish_reason": None}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"path":"/tmp/x"}'}}]},
                      "index": 0, "finish_reason": "tool_calls"}]},
    ]
    provider, client = _provider(_sse(events))
    try:
        got = await _collect(provider, _request())
        a = _assemble(got)
        blocks = a.blocks()
        assert [b.type for b in blocks] == ["reasoning", "tool-call"]
        assert blocks[0] == ReasoningBlock(text="think...")
        assert blocks[1].id == "call_1"
        assert blocks[1].name == "read_file"
        assert blocks[1].arguments == '{"path":"/tmp/x"}'
        assert a.finish.kind == "tool-calls"
    finally:
        await client.aclose()


async def test_usage_is_disjoint_cache_subtracted():
    events = [
        {"choices": [{"delta": {"content": "hi"}, "index": 0, "finish_reason": None}]},
        {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107,
                   "prompt_tokens_details": {"cached_tokens": 80}}},
    ]
    provider, client = _provider(_sse(events))
    try:
        got = await _collect(provider, _request())
        a = _assemble(got)
        assert a.usage == TokenUsage(input=20, output=7, cache_read=80)  # 100 - 80 cache
    finally:
        await client.aclose()


async def test_request_body_applies_deepseek_transforms():
    captured = {}

    def hook(request):
        captured["json"] = json.loads(request.content)
        captured["headers"] = request.headers

    provider, client = _provider(_sse([]), handler_hook=hook)
    try:
        messages = [
            create_system_message("sys"),
            create_user_message([ImageBlock(url="data:image/png;base64,AAAA")]),
            create_message(
                "assistant",
                [ToolCallBlock(id="c1", name="f", arguments="{}")],
                ModelSource(provider="deepseek", model="deepseek-chat"),
            ),
            create_tool_result_message("c1", [TextBlock(text='{"ok": true}')]),
        ]
        request = LLMRequest(
            provider="deepseek", model="deepseek-chat",
            messages=messages, max_tokens=100,
        )
        await _collect(provider, request)

        body = captured["json"]
        assert body["model"] == "deepseek-chat"
        assert body["stream"] is True
        assert body["max_tokens"] == 100
        wire = body["messages"]
        assert len(wire) == 4
        # image 块被剥成文本占位
        assert "image_url" not in json.dumps(wire[1]["content"])
        # assistant 携带 tool_calls + reasoning_content 回放
        assert wire[2]["tool_calls"][0]["function"]["name"] == "f"
        assert "reasoning_content" in wire[2]
        # tool 消息：wire role "tool" + 其 call id；正文来自 ToolResultBlock 内层
        assert wire[3]["role"] == "tool"
        assert wire[3]["tool_call_id"] == "c1"
        assert wire[3]["content"] == '{"ok": true}'
        assert captured["headers"]["authorization"] == "Bearer test-key"
    finally:
        await client.aclose()


async def test_http_error_is_error_finish_with_code():
    def handler(request):
        return httpx.Response(401, text="Unauthorized", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DeepSeekProvider(DeepSeekConfig(api_key="k"), client=client)
    try:
        got = await _collect(provider, _request())
        assert len(got) == 1
        assert got[0].type == "finish"
        assert got[0].reason.kind == "error"
        assert got[0].reason.failure.code == "AUTH"
    finally:
        await client.aclose()


async def test_signal_set_before_start_stops_with_aborted_finish():
    provider, client = _provider(_sse([
        {"choices": [{"delta": {"content": "should not be seen"}, "index": 0, "finish_reason": None}]},
    ]))
    try:
        signal = asyncio.Event()
        signal.set()
        got = [c async for c in provider.stream(_request(), signal=signal)]
        assert len(got) == 1
        assert got[0].type == "finish"
        assert got[0].reason.kind == "aborted"
    finally:
        await client.aclose()


async def test_signal_aborts_while_waiting_for_next_line():
    from llm.deepseek import _ABORT, _next_sse_line

    async def slow_lines():
        yield "data: {\"ok\": 1}"
        await asyncio.Event().wait()
        yield "data: [DONE]"

    signal = asyncio.Event()
    lines = slow_lines().__aiter__()
    first = await _next_sse_line(lines, signal)
    assert first.startswith("data:")
    signal.set()
    second = await asyncio.wait_for(_next_sse_line(lines, signal), timeout=0.5)
    assert second is _ABORT


async def test_empty_stop_is_emily_response_error():
    provider, client = _provider(_sse([
        {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]},
    ]))
    try:
        got = await _collect(provider, _request())
        a = _assemble(got)
        assert a.finish.kind == "error"
        assert a.finish.failure.code == "EMPTY_RESPONSE"
    finally:
        await client.aclose()
