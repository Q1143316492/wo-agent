"""事件溯源会话：模型可见历史由 append-only 日志派生。

dsh-session 的思想：日志是唯一事实源。``append`` 分配单调连续的 ``seq``
（恒等于日志长度）；从不修改或删除。``derive_messages()`` 把 surface 事件
（user/assistant/tool-result）投影成 provider 看到的 ``LLMMessage`` 列表。

投影走表层折叠：默认 ``append``；``surface_op: replace`` 用新节点替换当前
表层上 ``start``…``end`` 那段。被替换的事件仍在日志里，回放确定。

这刻意不是 pi 的"存富消息数组"模型：消息数组是*投影*，可从日志重新派生，
所以日志才是权威，重放/审计/fork 都免费。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from llm.types import LLMMessage

from .events import SessionEventData, SurfaceReplace, is_surface_event


@dataclass(frozen=True)
class SessionEvent:
    """一条日志项：事件本身加上它在日志中的位置和墙钟时间。"""

    seq: int  # 单调；追加时恒等于日志长度
    time: int  # epoch 毫秒
    event: SessionEventData


def derive_event_message(event: SessionEventData) -> LLMMessage | None:
    """把一条事件投影成它派生的 LLM 消息，或 None。

    非 surface 事件（边界、分片、tool/call、compaction/*）不产生消息。空内容的
    ``assistant/message`` 会被跳过：它只为承载 max-tokens 步的 usage，不能把
    一条没有内容的 assistant 回合塞进 provider 的 transcript。
    """
    if event.type == "user/message":
        return event.message
    if event.type == "assistant/message":
        if len(event.message.content) == 0:
            return None
        return event.message
    if event.type == "tool/result":
        return event.message
    return None


def fold_surface(events: list[SessionEvent]) -> list[tuple[int, LLMMessage]]:
    """按日志顺序折叠出当前表层：``(seq, message)`` 列表。

    ``append`` 加到尾部。``replace`` 的 ``start`` / ``end`` 必须是*当前*表层
    节点的 seq（含）；替换后表层顺序可以不再等于 seq 顺序。
    """
    nodes: list[tuple[int, LLMMessage]] = []
    for entry in events:
        msg = derive_event_message(entry.event)
        if msg is None:
            continue
        op = getattr(entry.event, "surface_op", "append")
        if op == "append":
            nodes.append((entry.seq, msg))
            continue
        if not isinstance(op, SurfaceReplace):
            raise ValueError(f"unknown surface_op: {op!r}")
        seqs = [seq for seq, _ in nodes]
        try:
            start_idx = seqs.index(op.start)
            end_idx = seqs.index(op.end)
        except ValueError as exc:
            raise ValueError(
                f"surface replace: start seq {op.start} or end seq {op.end} not found in surface"
            ) from exc
        if start_idx > end_idx:
            raise ValueError(
                f"surface replace: start seq {op.start} (index {start_idx}) "
                f"is after end seq {op.end} (index {end_idx})"
            )
        shadowed = [seq for seq, _ in nodes[start_idx : end_idx + 1]]
        sources = getattr(entry.event, "source_event_seqs", ())
        if sources:
            missing = [seq for seq in shadowed if seq not in sources]
            if missing:
                raise ValueError(
                    f"surface replace: source_event_seqs must include every shadowed "
                    f"surface node; missing {missing}"
                )
            later = [seq for seq in sources if seq >= entry.seq]
            if later:
                raise ValueError(
                    f"source_event_seqs must reference earlier events: {later} >= {entry.seq}"
                )
        nodes[start_idx : end_idx + 1] = [(entry.seq, msg)]
    return nodes


def _now_ms() -> int:
    return int(time.time() * 1000)


class Session:
    """一个 agent 交互的 append-only 事件日志。"""

    def __init__(self, session_id: str | None = None) -> None:
        self._id = session_id or uuid.uuid4().hex
        self._events: list[SessionEvent] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def seq(self) -> int:
        """下一条事件的序号 —— 恒等于日志长度。"""
        return len(self._events)

    @property
    def events(self) -> list[SessionEvent]:
        """append-only 日志的快照（调用方不能改它）。"""
        return list(self._events)

    def append(self, event: SessionEventData, time: int | None = None) -> SessionEvent:
        """追加一条类型化事件，返回它及分配到的 seq/time。

        ``time`` 默认取当前时间；持久化加载时传入存储的时间，让重载后的
        日志保留原始时间戳。
        """
        entry = SessionEvent(seq=len(self._events), time=time if time is not None else _now_ms(), event=event)
        self._events.append(entry)
        return entry

    def derive_messages(self) -> list[LLMMessage]:
        """从日志派生模型可见的消息历史。

        折叠表层后按表层顺序返回消息；边界、分片、tool/call、compaction/*
        不参与投影。被 replace 遮蔽的 surface 事件仍在 ``events`` 里。
        """
        return [message for _, message in fold_surface(self._events)]

    def surface_seqs(self) -> list[int]:
        """当前表层节点的 seq，顺序即模型看到的顺序。"""
        return [seq for seq, _ in fold_surface(self._events)]


__all__ = [
    "Session",
    "SessionEvent",
    "derive_event_message",
    "fold_surface",
    "is_surface_event",
]
