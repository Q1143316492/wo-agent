"""wo-agent — 工作区能力缝。

文件：``paths`` / ``text`` / ``tools``。本机命令：``shell`` + ``BashCapability``。
不是核心层。
"""

from .capability import BashCapability, WorkspaceCapability
from .errors import WorkspaceError
from .paths import WorkspacePaths
from .shell import BashResult, LocalBashRunner, find_bash
from .text import WorkspaceStore

__all__ = [
    "BashCapability",
    "BashResult",
    "LocalBashRunner",
    "WorkspaceCapability",
    "WorkspaceError",
    "WorkspacePaths",
    "WorkspaceStore",
    "find_bash",
]
