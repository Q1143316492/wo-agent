"""JSONL 持久化后端。

每个会话一个 JSONL 文件：首行 header（格式版本 + id），随后每行一个事件，
经 `serialize` 无损序列化。写入是原子的（写临时文件、fsync、改名），崩溃
不会留下半个文件。加载时，孤儿尾 turn（崩溃在半途）用合成的
`turn/end { reason: 'interrupted' }` 收尾，保留被中断的执行而不是截断——
dsh 的崩溃恢复思想。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .events import TurnEnd
from .persistence import SessionCorruptionError, SessionFormatUnsupportedError
from .serialize import dict_to_event, event_to_dict
from .session import Session


class JsonlSessionStore:
    FORMAT_VERSION = 1

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.jsonl"

    def save(self, session: Session) -> None:
        path = self._path(session.id)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            header = {"type": "session_header", "version": self.FORMAT_VERSION, "id": session.id}
            f.write(json.dumps(header, ensure_ascii=False) + "\n")
            for entry in session.events:
                row = {"seq": entry.seq, "time": entry.time, "event": event_to_dict(entry.event)}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)

    def load(self, session_id: str) -> Session | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        session: Session | None = None
        try:
            with open(path, encoding="utf-8") as f:
                header = json.loads(f.readline())
                if header.get("type") != "session_header":
                    raise SessionCorruptionError(f"{path}: missing session_header line")
                version = header.get("version")
                if version != self.FORMAT_VERSION:
                    raise SessionFormatUnsupportedError(
                        f"{path}: format version {version} is not readable (expected {self.FORMAT_VERSION})"
                    )
                session = Session(session_id=header["id"])
                for line in f:
                    row = json.loads(line)
                    session.append(dict_to_event(row["event"]), time=row.get("time"))
        except json.JSONDecodeError as e:
            raise SessionCorruptionError(f"{path}: malformed JSON: {e}") from e

        assert session is not None
        _repair_interrupted_turn(session)
        return session

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if path.exists():
            path.unlink()

    def list(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.jsonl")]


def _repair_interrupted_turn(session: Session) -> None:
    """用合成的 turn/end 关闭孤儿尾 turn（崩溃在半途）。"""
    started: set[int] = set()
    ended: set[int] = set()
    for entry in session.events:
        event = entry.event
        if event.type == "turn/start":
            started.add(event.turn)
        elif event.type == "turn/end":
            ended.add(event.turn)
    orphaned = started - ended
    if orphaned:
        session.append(TurnEnd(turn=max(orphaned), reason="interrupted"))
