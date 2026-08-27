"""两级 inbox：next-turn 与 next-step（对齐 dsh Inbox，不做持久 splice 事件）。

- followup → next-turn，唤醒
- steer → next-step，唤醒（当前轮下一步就看见）
- inject → next-step，不唤醒（idle 时一直等到下次唤醒）

claim 时先倒空 next-step，若本步是轮次开头再取一条 next-turn。被 claim 的
消息随后写成 ``user/message`` 才进 session——队列本身是活体状态。
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
