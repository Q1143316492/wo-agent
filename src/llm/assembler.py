"""增量分片到消息的组装器。

dsh-llm 的思想：适配器发出原始分片（block-start / delta / block-end /
usage / finish）；组装器是把分片变成内容块和最终 assistant 消息的**唯一共享
实现**。agent 循环把原始分片喂进来（可同时落日志供重放），流结束后读
``blocks()`` / ``usage`` / ``finish`` / ``message()``。

容忍纯 delta 协议（无 block-start/end）：对已被 ``block-end`` 关闭的 index
再来的 delta 会被忽略，因此一个行为异常的适配器无法破坏已完成的块。
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import (
    BlockEnd,
    BlockStart,
    ContentBlock,
    FinishChunk,
    FinishReason,
    LLMMessage,
    MessageSource,
    ModelSource,
    ReasoningBlock,
    ReasoningDelta,
    StreamChunk,
    TextBlock,
    TextDelta,
    ToolCallBlock,
    ToolCallDelta,
    TokenUsage,
    UsageChunk,
    create_message,
)


@dataclass
class _PartialBlock:
    block_type: str
    text: str = ""
    tool_call_id: str = ""
    tool_call_name: str | None = None
    tool_call_arguments: str = ""
    block: ContentBlock | None = None  # 由 block-end 设置；以它为准


class BlockAssembler:
    def __init__(self) -> None:
        self._partials: dict[int, _PartialBlock] = {}
        self._order: list[int] = []
        self._usage: TokenUsage | None = None
        self._finish: FinishReason | None = None

    def push(self, chunk: StreamChunk) -> None:
        if isinstance(chunk, BlockStart):
            if chunk.index not in self._partials:
                self._order.append(chunk.index)
                self._partials[chunk.index] = _PartialBlock(block_type=chunk.block_type)
            return

        if isinstance(chunk, TextDelta):
            partial = self._ensure(chunk.index, "text")
            if partial.block:
                return
            partial.text += chunk.text
            return

        if isinstance(chunk, ReasoningDelta):
            partial = self._ensure(chunk.index, "reasoning")
            if partial.block:
                return
            partial.text += chunk.text
            return

        if isinstance(chunk, ToolCallDelta):
            partial = self._ensure(chunk.index, "tool-call")
            if partial.block:
                return
            if chunk.id:
                partial.tool_call_id = chunk.id
            if chunk.name is not None:
                partial.tool_call_name = chunk.name
            partial.tool_call_arguments += chunk.arguments_delta
            return

        if isinstance(chunk, BlockEnd):
            partial = self._ensure(chunk.index, chunk.block.type)
            if partial.block:
                return  # 首次关闭为准
            partial.block = chunk.block
            return

        if isinstance(chunk, UsageChunk):
            self._usage = chunk.usage
            return

        if isinstance(chunk, FinishChunk):
            self._finish = chunk.reason
            return

    def _ensure(self, index: int, block_type: str) -> _PartialBlock:
        partial = self._partials.get(index)
        if partial is None:
            partial = _PartialBlock(block_type=block_type)
            self._partials[index] = partial
            self._order.append(index)
        return partial

    def _assemble(self, index: int) -> ContentBlock:
        partial = self._partials[index]
        if partial.block is not None:
            return partial.block
        if partial.block_type == "text":
            return TextBlock(text=partial.text)
        if partial.block_type == "reasoning":
            return ReasoningBlock(text=partial.text)
        if partial.block_type == "tool-call":
            return ToolCallBlock(
                id=partial.tool_call_id or f"call-{index}",
                name=partial.tool_call_name or "",
                arguments=partial.tool_call_arguments,
            )
        raise ValueError(f"cannot assemble incomplete block of type {partial.block_type!r}")

    def blocks(self) -> list[ContentBlock]:
        blocks = [self._assemble(index) for index in self._order]
        if self.finish.kind == "max-tokens":
            return [b for b in blocks if b.type != "tool-call"]
        return blocks

    @property
    def usage(self) -> TokenUsage | None:
        return self._usage

    @property
    def finish(self) -> FinishReason:
        return self._finish or FinishReason(kind="stop")

    def message(
        self,
        source: MessageSource | None = None,
        message_id: str | None = None,
    ) -> LLMMessage:
        source = source or ModelSource()
        return create_message(
            "assistant",
            self.blocks(),
            source,
            message_id=message_id,
        )
