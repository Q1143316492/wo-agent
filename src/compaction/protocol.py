"""压缩服务契约。

对齐 dsh-compaction 的 Service Definition：引擎判定要不要压、压哪一段；
摘要与阈值属于后端。``compact/*`` 事件在 ``session.events``。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal, Protocol

from llm.types import PluginSource
from session import Session

CompactionTrigger = Literal["pressure", "overflow"]

COMPACT_PLUGIN = "compact"


def compact_checkpoint_source(compaction_id: str) -> PluginSource:
    """替换节点的 provenance：把检查点关联到一次 compaction 事务。"""
    return PluginSource(plugin=COMPACT_PLUGIN, compaction_id=compaction_id)


def is_compact_checkpoint_source(source) -> bool:
    return getattr(source, "kind", None) == "plugin" and getattr(source, "plugin", None) == COMPACT_PLUGIN


class CompactionBusy(Exception):
    """日志里已有未闭合的 ``compaction/start``。"""


@dataclass(frozen=True)
class CompactionResult:
    compaction_id: str
    start_seq: int
    summary_seq: int
    end_seq: int
    summary: str
    shadowed_range: tuple[int, int]
    shadowed_seqs: tuple[int, ...]
    shadowed_chars: int


class Summarizer(Protocol):
    """把一段表层消息压成纯文本摘要。实现方直接调 LLM，不走 agent 循环。"""

    async def summarize(
        self,
        messages: list,
        signal: asyncio.Event | None = None,
    ) -> str:
        ...


class CompactionEngine(Protocol):
    async def compact_if_needed(
        self,
        session: Session,
        *,
        trigger: CompactionTrigger,
        signal: asyncio.Event | None = None,
        turn: int | None = None,
    ) -> CompactionResult | None:
        """``pressure`` 看阈值；``overflow`` 跳过阈值、仍要有可切的平衡范围。"""
        ...

    async def compact_now(
        self,
        session: Session,
        signal: asyncio.Event | None = None,
    ) -> CompactionResult | None:
        """未达压力也压一段较早范围；没有可切范围则不写日志。"""
        ...
