"""把 Session 写成一个 .jsonl，再读回来。

save 先写完再改名，避免崩溃留下半个文件。load 时若 turn 开了没结束，
补一条 turn/end { reason: "interrupted" }：半截执行还在，不当损坏扔掉。
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
            header = {"type": "session_header", "version": self.FORMAT_VERSION, "id": session.id, "title": session.title}
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
                session.title = header.get("title") or ""
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
        paths = list(self._dir.glob("*.jsonl"))
        paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [p.stem for p in paths]


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
