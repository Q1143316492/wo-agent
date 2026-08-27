"""把压缩引擎挂到 ``ctx.compaction``。循环只消费这个槽，不 import 本包实现。"""

from __future__ import annotations

from .engine import BasicCompaction, CompactionOptions
from .protocol import Summarizer


class CompactionCapability:
    def __init__(self, summarizer: Summarizer, options: CompactionOptions | None = None) -> None:
        self._engine = BasicCompaction(summarizer, options)

    def mount(self, ctx) -> None:
        ctx.compaction = self._engine
