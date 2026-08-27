"""wo-agent — 上下文压缩。

判定派生历史是否过大，把较早表层范围摘要成一条 ``user/message``，用
``surfaceOp: replace`` 改投影。日志不删。摘要走 ``provider.stream()``，
不是 agent 的一步。
"""

from .capability import CompactionCapability
from .engine import BasicCompaction, CompactionOptions
from .protocol import (
    CompactionBusy,
    CompactionEngine,
    CompactionResult,
    CompactionTrigger,
    Summarizer,
    compact_checkpoint_source,
    is_compact_checkpoint_source,
)
from .summarizer import LlmSummarizer, frame_summary

__all__ = [
    "BasicCompaction",
    "CompactionBusy",
    "CompactionCapability",
    "CompactionEngine",
    "CompactionOptions",
    "CompactionResult",
    "CompactionTrigger",
    "LlmSummarizer",
    "Summarizer",
    "compact_checkpoint_source",
    "frame_summary",
    "is_compact_checkpoint_source",
]
