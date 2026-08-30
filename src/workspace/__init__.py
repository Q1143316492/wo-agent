"""wo-agent — 工作区能力缝。

文件：``paths`` / ``text`` / ``tools``。本机命令：``shell`` + ``BashCapability``。
搜文件：``search`` + ``SearchCapability``（spawn 本机 ``rg``）。
不是核心层。
"""

from .capability import BashCapability, SearchCapability, WorkspaceCapability
from .errors import WorkspaceError
from .paths import WorkspacePaths
from .search import LocalRipgrepRunner, SearchResult, resolve_rg
from .shell import BashResult, LocalBashRunner, find_bash
from .text import WorkspaceStore

__all__ = [
    "BashCapability",
    "BashResult",
    "LocalBashRunner",
    "LocalRipgrepRunner",
    "SearchCapability",
    "SearchResult",
    "WorkspaceCapability",
    "WorkspaceError",
    "WorkspacePaths",
    "WorkspaceStore",
    "find_bash",
    "resolve_rg",
]
