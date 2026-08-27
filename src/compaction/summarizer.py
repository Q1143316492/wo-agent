"""默认摘要：直接 ``provider.stream()``，不走 agent 循环。

对齐 dsh-compaction-basic 的指令与检查点装帧。不做 KV cache 对齐
（不回放系统提示词/工具 schema），摘要调用只带被压消息 + 指令。
"""

from __future__ import annotations

import asyncio

from llm.assembler import BlockAssembler
from llm.protocol import LLMProvider, LLMRequest
from llm.types import LLMMessage, PluginSource, TextBlock, create_message

COMPACTION_INSTRUCTION = (
    "You are now acting as a compaction engine. Condense the conversation ABOVE "
    "into a structured checkpoint that lets another model resume with no loss of "
    "essential context.\n\n"
    "Output EXACTLY the Markdown structure below: keep every section, in order. "
    "Use terse bullets, not prose. Write \"(none)\" for an empty section.\n\n"
    "## Primary Request and Intent\n"
    "- [the user's original and evolving goals]\n\n"
    "## Key Technical Concepts\n"
    "- [technologies, patterns, conventions]\n\n"
    "## Files and Code\n"
    "- [exact path: why it matters]\n\n"
    "## Errors and Fixes\n"
    "- [error: how it was resolved]\n\n"
    "## Pending Jobs\n"
    "- [requested work not yet completed]\n\n"
    "## Current Work\n"
    "- [what was in progress at this checkpoint]\n\n"
    "## Next Step\n"
    "- [the single next action, or \"(none)\"]\n\n"
    "## Critical Context\n"
    "- [decisions, constraints, open questions]\n\n"
    "Rules:\n"
    "- Preserve exact file paths, commands, error strings, identifiers.\n"
    "- Do NOT mention this summarization request.\n"
    "- Output only the checkpoint text; do not call any tool."
)

CHECKPOINT_PREAMBLE = (
    "This is an automatically generated checkpoint condensing an earlier span of "
    "the conversation to free up context. Treat the captured context as established "
    "background and build on it without restating it. Continue the task directly "
    "from the messages that follow, without acknowledging this checkpoint."
)

SUMMARY_OPEN_TAG = "<compacted-summary>"
SUMMARY_CLOSE_TAG = "</compacted-summary>"


def frame_summary(summary: str) -> str:
    """把摘要包进检查点装帧，成为替换 user 消息的正文。"""
    body = summary.strip()
    return f"{CHECKPOINT_PREAMBLE}\n\n{SUMMARY_OPEN_TAG}\n{body}\n{SUMMARY_CLOSE_TAG}"


class LlmSummarizer:
    """用同一套 LLMProvider 做一次无工具的摘要调用。"""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        provider_name: str,
        model: str,
        max_tokens: int = 1024,
    ) -> None:
        self._provider = provider
        self._provider_name = provider_name
        self._model = model
        self._max_tokens = max_tokens

    async def summarize(
        self,
        messages: list[LLMMessage],
        signal: asyncio.Event | None = None,
    ) -> str:
        instruction = create_message(
            "user",
            [TextBlock(text=COMPACTION_INSTRUCTION)],
            PluginSource(plugin="compaction"),
        )
        request = LLMRequest(
            provider=self._provider_name,
            model=self._model,
            messages=[*messages, instruction],
            max_tokens=self._max_tokens,
        )
        assembler = BlockAssembler()
        async for chunk in self._provider.stream(request, signal=signal):
            assembler.push(chunk)
        finish = assembler.finish
        if finish is None:
            raise RuntimeError("summarization stream ended without finish")
        if finish.kind in ("error", "aborted"):
            failure = finish.failure
            message = failure.message if failure is not None else finish.kind
            raise RuntimeError(f"summarization failed: {message}")
        if finish.kind == "max-tokens":
            raise RuntimeError("summarization truncated at the token cap")
        texts = [block.text for block in assembler.blocks() if block.type == "text"]
        summary = "".join(texts).strip()
        if not summary:
            raise RuntimeError("summarization produced no text summary content")
        return summary
