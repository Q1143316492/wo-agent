"""会话持久化缝。

dsh session-persistence 的思想：持久化是一个能力缝。接口在同一套
`SessionEvent` 词汇上定义 save/load/delete/list——不造平行持久化类型——
由后端实现（先 JSONL，后 SQLite）。这个缝让会话层与存储解耦。
"""

from __future__ import annotations

from typing import Protocol

from .session import Session


class SessionStore(Protocol):
    """持久化的 append-only 会话存储。"""

    def save(self, session: Session) -> None:
        """持久化一个会话的完整事件日志（header + 事件）。"""
        ...

    def load(self, session_id: str) -> Session | None:
        """加载一个会话；没有该 id 的存储会话时返回 None。"""
        ...

    def delete(self, session_id: str) -> None:
        """删除一个存储会话的产物。"""
        ...

    def list(self) -> list[str]:
        """所有已存储的会话 id。"""
        ...


class SessionFormatUnsupportedError(Exception):
    """存储日志用了当前构建无法读取的格式版本。"""


class SessionCorruptionError(Exception):
    """存储日志损坏，无法忠实重建。"""
