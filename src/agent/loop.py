"""在一个 Session 上跑循环：写日志、调 provider.stream、跑 tools.execute。

followup / steer / inject / enqueue 只把话推进 Inbox，claim 之后才 append
UserMessageEvent——所以 idle 时 inject，session.events 仍是空的。
拼请求用 derive_messages()；系统提示词每步 assemble()，不写进 session。
stream 失败若 is_retryable，同一步再请求，不写 assistant/message。
有 compaction 时，请求前 compact_if_needed("pressure")；
CONTEXT_WINDOW_EXCEEDED 再 compact_if_needed("overflow") 后重试该步。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Literal

from llm.assembler import BlockAssembler
from llm.errors import CONTEXT_WINDOW_EXCEEDED, is_retryable
from llm.protocol import LLMProvider, LLMRequest
from llm.types import (
    LLMMessage,
    LlmCallConfig,
    ModelSource,
    PluginSource,
    StreamChunk,
    TextBlock,
    create_message,
    create_model_message,
    create_tool_result_message,
    create_user_message,
)
from session import Session
from session.events import (
    AssistantChunk,
    AssistantMessageEvent,
    RequestHeaderEvent,
    StepEnd,
    StepStart,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)

from .agent import AgentOptions, AgentStatus
from .inbox import Inbox, InboxTarget
from system_prompt import SystemPromptRegistry
from tools import ToolExecutor

StepEndKind = Literal["completed", "tool-calls", "max-tokens", "error", "aborted"]


def _user_text(message: LLMMessage) -> str:
    return "".join(block.text for block in message.content if getattr(block, "type", None) == "text")


class ReactLoopAgent:
    """把 followup / steer / inject / enqueue 跑成 turn 和 step，并写入 session。"""

    def __init__(
        self,
        session: Session,
        provider: LLMProvider,
        options: AgentOptions,
        tools: ToolExecutor,
        system_prompt: SystemPromptRegistry | None = None,
        compaction=None,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> None:
        self._session = session
        self._provider = provider
        self._options = options
        self._tools = tools
        self._system_prompt = system_prompt
        self._compaction = compaction
        self._on_chunk = on_chunk
        self._inbox = Inbox()
        self._status: AgentStatus = "idle"
        self._cancel = asyncio.Event()
        self._activity: asyncio.Future[None] | None = None

    # ---- 公开契约 ----

    @property
    def id(self) -> str:
        return self._session.id

    @property
    def session(self) -> Session:
        return self._session

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def followup(self, text: str) -> None:
        self._inbox.push_turn(create_user_message([TextBlock(text=text)]))
        await self._ensure_running()

    async def steer(self, text: str) -> None:
        self._inbox.push_step(create_user_message([TextBlock(text=text)]))
        await self._ensure_running()

    def inject(self, text: str) -> None:
        self._inbox.push_step(create_user_message([TextBlock(text=text)]))

    def enqueue(self, text: str) -> None:
        self._inbox.push_turn(create_user_message([TextBlock(text=text)]))

    def queued(self) -> tuple[tuple[str, str], ...]:
        return tuple((message.id, _user_text(message)) for message in self._inbox.peek_turns())

    def take_back(self) -> str | None:
        message = self._inbox.pop_last_turn()
        if message is None:
            return None
        return _user_text(message)

    def cancel(self, cause: str, *, keep_inbox: bool = False) -> None:
        if not keep_inbox:
            self._inbox.clear()
        self._cancel.set()

    async def when_idle(self) -> None:
        while self._activity is not None:
            await self._activity

    async def _ensure_running(self) -> None:
        """Idle 则开驱动；已在跑则等到静下来。队列若在收尾时漏接，再开一轮。"""
        while self._inbox.has_pending or self._status == "running":
            if self._status == "idle":
                if not self._inbox.has_pending:
                    return
                await self._run()
            else:
                await self.when_idle()

    # ---- 驱动 ----

    async def _run(self) -> None:
        self._cancel = asyncio.Event()
        self._status = "running"
        loop = asyncio.get_running_loop()
        activity: asyncio.Future[None] = loop.create_future()
        self._activity = activity
        try:
            while not self._cancel.is_set():
                await self._run_turn(self._next_turn())
                if not self._inbox.has_pending:
                    break
        finally:
            self._status = "idle"
            self._activity = None
            if not activity.done():
                activity.set_result(None)

    def _next_turn(self) -> int:
        turn = 0
        for entry in self._session.events:
            if entry.event.type == "turn/start":
                turn = max(turn, entry.event.turn)
        return turn + 1

    def _config(self) -> LlmCallConfig:
        return LlmCallConfig(
            provider=self._options.provider,
            model=self._options.model,
            max_tokens=self._options.max_tokens,
            temperature=self._options.temperature,
        )

    def _build_messages(self):
        messages = self._session.derive_messages()
        prompt = self._system_prompt.assemble() if self._system_prompt is not None else ""
        if prompt:
            system = create_message(
                "system",
                [TextBlock(text=prompt)],
                PluginSource(plugin="system-prompt"),
            )
            messages = [system, *messages]
        return messages

    async def _run_turn(self, turn: int) -> None:
        session = self._session
        session.append(TurnStart(turn=turn))
        end_reason = "completed"
        step = 0
        target: InboxTarget = "next-turn"
        try:
            while not self._cancel.is_set():
                claimed = self._inbox.claim(target)
                if step == 0 and not claimed:
                    break
                for message in claimed:
                    session.append(UserMessageEvent(message=message))

                step += 1
                session.append(StepStart(turn=turn, step=step))
                kind = await self._run_step(turn, step)
                session.append(StepEnd(turn=turn, step=step))

                if self._cancel.is_set() or kind == "aborted":
                    end_reason = "aborted"
                    break
                if kind in ("error", "max-tokens"):
                    end_reason = kind
                    if not self._inbox.has_step:
                        break
                    target = "next-step"
                    continue
                if kind == "tool-calls":
                    target = "next-step"
                    continue
                if not self._inbox.has_step:
                    break
                target = "next-step"
        finally:
            if self._cancel.is_set():
                end_reason = "aborted"
            session.append(TurnEnd(turn=turn, reason=end_reason))

    async def _maybe_compact(self, trigger: str, turn: int):
        if self._compaction is None:
            return None
        return await self._compaction.compact_if_needed(
            self._session, trigger=trigger, signal=self._cancel, turn=turn
        )

    async def _run_step(self, turn: int, step: int) -> StepEndKind:
        """一次模型调用（可重试）+ 可选顺序工具。失败不写 assistant/message。"""
        session = self._session
        attempts = 0
        overflow_compacted = False
        while True:
            if not overflow_compacted:
                await self._maybe_compact("pressure", turn)
            reason = (
                "initial"
                if step == 1 and attempts == 0 and not overflow_compacted
                else ("retry" if attempts else "change")
            )
            session.append(RequestHeaderEvent(header=self._config(), reason=reason))

            request = LLMRequest(
                provider=self._options.provider,
                model=self._options.model,
                messages=self._build_messages(),
                max_tokens=self._options.max_tokens,
                temperature=self._options.temperature,
                tools=tuple(self._tools.schemas()),
            )

            assembler = BlockAssembler()
            async for chunk in self._provider.stream(request, signal=self._cancel):
                session.append(AssistantChunk(turn=turn, step=step, chunk=chunk))
                assembler.push(chunk)
                if self._on_chunk is not None:
                    self._on_chunk(chunk)

            finish = assembler.finish
            if finish.kind == "aborted" or self._cancel.is_set():
                return "aborted"
            if finish.kind == "error":
                code = finish.failure.code if finish.failure is not None else ""
                if (
                    code == CONTEXT_WINDOW_EXCEEDED
                    and self._compaction is not None
                    and not overflow_compacted
                ):
                    result = await self._maybe_compact("overflow", turn)
                    if result is not None:
                        overflow_compacted = True
                        continue
                attempts += 1
                if is_retryable(code) and attempts <= self._options.max_retries:
                    if self._options.retry_backoff_s > 0:
                        await asyncio.sleep(self._options.retry_backoff_s * attempts)
                    continue
                return "error"

            source = ModelSource(provider=self._options.provider, model=self._options.model)
            session.append(
                AssistantMessageEvent(
                    turn=turn,
                    step=step,
                    message=create_model_message(assembler.blocks(), source),
                    usage=assembler.usage,
                )
            )
            if finish.kind == "max-tokens":
                return "max-tokens"

            tool_calls = [b for b in assembler.blocks() if b.type == "tool-call"]
            if not tool_calls:
                return "completed"
            for call in tool_calls:
                if self._cancel.is_set():
                    return "aborted"
                session.append(
                    ToolCallEvent(turn=turn, step=step, call_id=call.id, name=call.name, arguments=call.arguments)
                )
                result = await self._tools.execute(
                    call.name, call.arguments, cancel=self._cancel
                )
                message = create_tool_result_message(call.id, result.content, is_error=result.is_error)
                session.append(ToolResultEvent(turn=turn, step=step, message=message))
                if self._cancel.is_set():
                    return "aborted"
            return "tool-calls"
