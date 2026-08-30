"""DeepSeek provider 适配器（OpenAI 兼容 /chat/completions，SSE 流）。

吸收自 UTAgent 验证过的 DeepSeek 特例行为，以及 dsh-llm-deepseek/translate
的分片翻译思想：

- assistant 消息回放 ``reasoning_content``（空串也可）以支持多轮工具调用回放。
- DeepSeek 不接受 ``image_url`` 输入——剥成占位文本。
- ``prompt_tokens`` 含缓存命中；usage 映射为 disjoint 计数。
- ``block-end`` / ``usage`` / ``finish`` 延迟到 ``[DONE]`` 才发，保证终止
  finish 之后没有别的东西、usage 在它之前。
- 无任何打开的块却以 ``stop`` 结束时，是 ``EMPTY_RESPONSE`` 错误终止。
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import httpx

from .errors import (
    ABORTED,
    AUTH,
    CONTEXT_WINDOW_EXCEEDED,
    EMPTY_RESPONSE,
    MALFORMED_RESPONSE,
    QUOTA_EXCEEDED,
    RATE_LIMIT,
    STREAM_CLOSED,
)
from .protocol import LLMProvider, LLMRequest
from .types import (
    BlockEnd,
    BlockStart,
    ContentBlock,
    FinishChunk,
    FinishReason,
    ImageBlock,
    LLMMessage,
    LlmFailure,
    ReasoningBlock,
    ReasoningDelta,
    StreamChunk,
    TextBlock,
    TextDelta,
    TokenUsage,
    ToolCallBlock,
    ToolCallDelta,
    ToolResultBlock,
    UsageChunk,
)

DONE = "[DONE]"
_IMAGE_PLACEHOLDER = "[image not supported by deepseek]"
_ABORT = object()


async def _next_sse_line(lines, signal):
    """下一行，或取消。阻塞在 ``aiter_lines`` 时也要能被 ``signal`` 打断。"""
    if signal is None:
        try:
            return await anext(lines)
        except StopAsyncIteration:
            return None
    if signal.is_set():
        return _ABORT
    read = asyncio.create_task(anext(lines, None))
    wait = asyncio.create_task(signal.wait())
    done, pending = await asyncio.wait({read, wait}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in pending:
        try:
            await task
        except asyncio.CancelledError:
            pass
    if wait in done:
        return _ABORT
    return read.result()


async def sse_payloads(resp, signal):
    """按行切开 HTTP 流。普通行是一段 JSON，最后一行是 ``[DONE]``。"""
    lines = resp.aiter_lines()
    while True:
        line = await _next_sse_line(lines, signal)
        if line is _ABORT:
            yield ("abort", None)
            return
        if line is None:
            return
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        if payload == DONE:
            yield ("done", None)
            return
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            yield ("malformed", payload[:120])
            return
        yield ("data", data)


class DeepSeekConfig:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout


def map_finish_reason(reason: str) -> FinishReason:
    if reason == "stop":
        return FinishReason(kind="stop")
    if reason == "tool_calls":
        return FinishReason(kind="tool-calls")
    if reason == "length":
        return FinishReason(kind="max-tokens")
    return FinishReason(
        kind="error",
        failure=LlmFailure(message=f"model stopped: {reason}", code=reason.upper()),
    )


def map_usage(usage: dict) -> TokenUsage:
    """把 wire usage 映射成 DISJOINT 计数（DeepSeek 的 prompt_tokens 含缓存）。"""
    prompt_details = usage.get("prompt_tokens_details") or {}
    cached = prompt_details.get("cached_tokens") or usage.get("prompt_cache_hit_tokens") or 0
    completion_details = usage.get("completion_tokens_details") or {}
    return TokenUsage(
        input=max(0, usage.get("prompt_tokens", 0) - cached),
        output=usage.get("completion_tokens", 0),
        cache_read=cached,
        reasoning=completion_details.get("reasoning_tokens") or 0,
    )


def close_block(block: dict) -> ContentBlock:
    if block["kind"] == "text":
        return TextBlock(text=block["text"])
    if block["kind"] == "reasoning":
        return ReasoningBlock(text=block["text"])
    return ToolCallBlock(
        id=block.get("call_id", ""),
        name=block.get("name", ""),
        arguments=block["text"],
    )


def http_code(status: int) -> str:
    if status in (401, 403):
        return AUTH
    if status == 429:
        return RATE_LIMIT
    if status in (402, 409):
        return QUOTA_EXCEEDED
    if status == 400:
        return CONTEXT_WINDOW_EXCEEDED
    return "HTTP"


def _error_finish(message: str, code: str, status: int | None = None) -> FinishChunk:
    return FinishChunk(
        reason=FinishReason(kind="error", failure=LlmFailure(message=message, code=code, status=status))
    )


def _aborted_finish() -> FinishChunk:
    return FinishChunk(reason=FinishReason(kind="aborted", failure=LlmFailure(message="aborted", code=ABORTED)))


class _Translator:
    """把多行 JSON 攒成一次完整回复。行与行之间要记住已经吐出了哪些字。"""

    def __init__(self) -> None:
        self._next_index = 0
        self._text: dict | None = None
        self._reasoning: dict | None = None
        self._tools: dict[int, dict] = {}
        self._order: list[dict] = []
        self._pending_finish: FinishReason | None = None
        self._pending_usage: TokenUsage | None = None

    def _open(self, kind: str) -> dict:
        block = {"index": self._next_index, "kind": kind, "text": ""}
        self._next_index += 1
        self._order.append(block)
        return block

    def translate(self, data: dict) -> list[StreamChunk]:
        """把一个 SSE choice payload 映射成分片，并更新块状态。"""
        out: list[StreamChunk] = []
        for choice in data.get("choices") or []:
            delta = choice.get("delta") or {}
            self._reasoning_deltas(delta, out)
            self._text_deltas(delta, out)
            self._tool_call_deltas(delta, out)
            finish = choice.get("finish_reason")
            if isinstance(finish, str):
                self._pending_finish = map_finish_reason(finish)
        if data.get("usage"):
            self._pending_usage = map_usage(data["usage"])
        return out

    def _reasoning_deltas(self, delta: dict, out: list[StreamChunk]) -> None:
        reasoning = delta.get("reasoning_content")
        if not (isinstance(reasoning, str) and reasoning):
            return
        if self._reasoning is None:
            self._reasoning = self._open("reasoning")
            out.append(BlockStart(index=self._reasoning["index"], block_type="reasoning"))
        self._reasoning["text"] += reasoning
        out.append(ReasoningDelta(index=self._reasoning["index"], text=reasoning))

    def _text_deltas(self, delta: dict, out: list[StreamChunk]) -> None:
        content = delta.get("content")
        if not (isinstance(content, str) and content):
            return
        if self._text is None:
            self._text = self._open("text")
            out.append(BlockStart(index=self._text["index"], block_type="text"))
        self._text["text"] += content
        out.append(TextDelta(index=self._text["index"], text=content))

    def _tool_call_deltas(self, delta: dict, out: list[StreamChunk]) -> None:
        for call in delta.get("tool_calls") or []:
            index = call.get("index", 0)
            block = self._tools.get(index)
            if block is None:
                block = self._open("tool-call")
                self._tools[index] = block
                out.append(BlockStart(index=block["index"], block_type="tool-call"))
            if call.get("id") is not None:
                block["call_id"] = call["id"]
            fn = call.get("function") or {}
            if fn.get("name") is not None:
                block["name"] = fn["name"]
            fragment = fn.get("arguments") or ""
            block["text"] += fragment
            out.append(
                ToolCallDelta(
                    index=block["index"],
                    id=block.get("call_id", ""),
                    name=block.get("name"),
                    arguments_delta=fragment,
                )
            )

    def flush(self) -> list[StreamChunk]:
        out: list[StreamChunk] = []
        for block in self._order:
            out.append(BlockEnd(index=block["index"], block=close_block(block)))
        if self._pending_usage is not None:
            out.append(UsageChunk(usage=self._pending_usage))
        reason = self._pending_finish or FinishReason(kind="stop")
        if reason.kind == "stop" and not self._order:
            reason = FinishReason(
                kind="error",
                failure=LlmFailure(
                    message="model returned a completed response with no content",
                    code=EMPTY_RESPONSE,
                ),
            )
        out.append(FinishChunk(reason=reason))
        return out


async def _read_reply(resp, signal) -> AsyncIterator[StreamChunk]:
    """读模型的流式回复。

    DeepSeek 的响应长这样（一行一个事件）::

        data: {"choices":[{"delta":{"content":"2"}}]}
        data: {"choices":[{"delta":{"content":"。"}}]}
        data: [DONE]

    前面的行是还在生成；``[DONE]`` 表示说完了。
    """
    if resp.status_code != 200:
        text = (await resp.aread()).decode("utf-8", "replace")
        yield _error_finish(
            f"HTTP {resp.status_code}: {text[:500]}",
            http_code(resp.status_code),
            resp.status_code,
        )
        return

    translator = _Translator()
    async for kind, data in sse_payloads(resp, signal):
        if kind == "data":
            for chunk in translator.translate(data):
                yield chunk
            continue
        if kind == "done":
            for chunk in translator.flush():
                yield chunk
            return
        if kind == "abort":
            yield _aborted_finish()
            return
        yield _error_finish("malformed SSE payload", MALFORMED_RESPONSE)
        return
    yield _error_finish("SSE stream ended without [DONE]", STREAM_CLOSED)


class DeepSeekProvider:
    def __init__(
        self,
        config: DeepSeekConfig | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or DeepSeekConfig()
        # 注入 client（如 httpx.MockTransport）让测试不碰网络。
        self._client = client

    async def stream(
        self,
        request: LLMRequest,
        signal: asyncio.Event | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """发一次请求，把模型的流式回复逐段交出去。失败也走分片，不抛。"""
        body = self._build_body(request)
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._config.base_url}/chat/completions"
        if signal is not None and signal.is_set():
            yield _aborted_finish()
            return
        owns_client = self._client is None
        client = self._client if self._client is not None else httpx.AsyncClient(timeout=self._config.timeout)
        try:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                async for chunk in _read_reply(resp, signal):
                    yield chunk
        finally:
            if owns_client:
                await client.aclose()

    def _build_body(self, request: LLMRequest) -> dict:
        body: dict = {
            "model": request.model,
            "messages": [self._to_openai_dict(m) for m in request.messages],
            "stream": True,
        }
        max_tokens = request.max_tokens or self._config.max_tokens
        if max_tokens:
            body["max_tokens"] = max_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.stop:
            body["stop"] = list(request.stop)
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
        return body

    def _to_openai_dict(self, msg: LLMMessage) -> dict:
        """把 provider 中立的 LLMMessage 映射成 OpenAI/DeepSeek wire 形态。"""
        tool_results = [b for b in msg.content if isinstance(b, ToolResultBlock)]
        is_tool = bool(tool_results)
        d: dict = {"role": "tool" if is_tool else msg.role}

        parts: list[str] = []
        for block in msg.content:
            if isinstance(block, TextBlock):
                parts.append(block.text)
            elif isinstance(block, ImageBlock):
                parts.append(_IMAGE_PLACEHOLDER)
            elif isinstance(block, ToolResultBlock):
                for inner in block.content:
                    if isinstance(inner, TextBlock) and inner.text:
                        parts.append(inner.text)
        d["content"] = "".join(parts) if parts else ""

        if msg.role == "assistant":
            tool_calls = [b for b in msg.content if isinstance(b, ToolCallBlock)]
            if tool_calls:
                d["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in tool_calls
                ]
            reasoning = next((b.text for b in msg.content if isinstance(b, ReasoningBlock)), None)
            d["reasoning_content"] = reasoning if reasoning is not None else ""
        elif is_tool:
            d["tool_call_id"] = tool_results[0].tool_call_id

        return d
