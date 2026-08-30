"""两级 inbox：next-turn 与 next-step（对齐 dsh Inbox，不做持久 splice 事件）。

- followup / enqueue → next-turn
- steer / inject → next-step
- claim 时先倒空 next-step，若本步是轮次开头再取一条 next-turn

队列是活体：claim 之后才写成 ``user/message``。
"""

from __future__ import annotations

from typing import Literal

from llm.types import LLMMessage

InboxTarget = Literal["next-turn", "next-step"]


class Inbox:
    def __init__(self) -> None:
        self._next_turn: list[LLMMessage] = []
        self._next_step: list[LLMMessage] = []

    def push_turn(self, message: LLMMessage) -> None:
        self._next_turn.append(message)

    def push_step(self, message: LLMMessage) -> None:
        self._next_step.append(message)

    def peek_turns(self) -> tuple[LLMMessage, ...]:
        return tuple(self._next_turn)

    def pop_last_turn(self) -> LLMMessage | None:
        if not self._next_turn:
            return None
        return self._next_turn.pop()

    def clear(self) -> None:
        self._next_turn.clear()
        self._next_step.clear()

    @property
    def has_pending(self) -> bool:
        return bool(self._next_turn or self._next_step)

    @property
    def has_step(self) -> bool:
        return bool(self._next_step)

    def claim(self, target: InboxTarget) -> list[LLMMessage]:
        claimed = list(self._next_step)
        self._next_step.clear()
        if target == "next-turn" and self._next_turn:
            claimed.append(self._next_turn.pop(0))
        return claimed
