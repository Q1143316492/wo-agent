"""围栏内的 UTF-8 文本读写与字面量编辑。

``edit`` 对齐 dsh ``fs-local``：匹配前把 ``\\r\\n`` 收成 ``\\n``，写回按原文件
主要换行风格还原。不做版本 CAS、不做 observation policy。写入先落临时文件
再 ``os.replace``，避免半截文件。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .errors import WorkspaceError
from .paths import WorkspacePaths

MAX_FILE_BYTES = 10 * 1024 * 1024


def normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def detect_line_endings(raw: str) -> str:
    sample = raw[:4096]
    crlf = sample.count("\r\n")
    lf = sample.count("\n") - crlf
    return "CRLF" if crlf > lf else "LF"


def restore_line_endings(content: str, style: str) -> str:
    if style == "LF":
        return content
    return "\r\n".join(normalize_lf(content).split("\n"))


def count_occurrences(content: str, needle: str) -> int:
    count = 0
    index = 0
    while True:
        found = content.find(needle, index)
        if found < 0:
            return count
        count += 1
        index = found + len(needle)


def apply_literal_edit(content: str, old_string: str, new_string: str, replace_all: bool, display: str) -> str:
    old_norm = normalize_lf(old_string)
    if not old_norm:
        raise WorkspaceError("old_string must be a non-empty string", "EDIT_NOT_FOUND")
    new_norm = normalize_lf(new_string)
    replacements = count_occurrences(content, old_norm)
    if replacements == 0:
        raise WorkspaceError(f'old_string was not found in "{display}"', "EDIT_NOT_FOUND")
    if not replace_all and replacements > 1:
        raise WorkspaceError(
            f'old_string matched {replacements} times in "{display}"; '
            "provide a more specific old_string or set replace_all to true",
            "AMBIGUOUS_EDIT",
        )
    return content.replace(old_norm, new_norm)


def _decode_utf8(data: bytes, display: str, verb: str) -> str:
    if b"\x00" in data:
        raise WorkspaceError(f'cannot {verb} "{display}": binary file', "NOT_TEXT")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WorkspaceError(f'cannot {verb} "{display}": not valid UTF-8', "NOT_TEXT") from error


def _atomic_write(path: Path, content: str, display: str) -> None:
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise WorkspaceError(f'cannot write "{display}": file exceeds {MAX_FILE_BYTES} bytes', "FILE_TOO_LARGE")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".wo-write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class WorkspaceStore:
    """一个根下的文本存储。工具层只依赖本对象，不直接拼路径。"""

    def __init__(self, paths: WorkspacePaths) -> None:
        self.paths = paths

    def _existing_file(self, path: Path, display: str, verb: str) -> None:
        if not path.exists():
            raise WorkspaceError(f'cannot {verb} "{display}": not found', "NOT_FOUND")
        if not path.is_file():
            raise WorkspaceError(f'cannot {verb} "{display}": not a regular file', "NOT_REGULAR_FILE")

    def read_bytes(self, file_path: str, verb: str = "read") -> tuple[str, Path, bytes]:
        path = self.paths.resolve(file_path)
        display = self.paths.display(path)
        self._existing_file(path, display, verb)
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise WorkspaceError(
                f'cannot {verb} "{display}": file exceeds {MAX_FILE_BYTES} bytes',
                "FILE_TOO_LARGE",
            )
        return display, path, path.read_bytes()

    def read_text(self, file_path: str) -> tuple[str, str]:
        display, _path, data = self.read_bytes(file_path, "read")
        return display, _decode_utf8(data, display, "read")

    def write_text(self, file_path: str, content: str) -> tuple[str, str]:
        if not isinstance(content, str):
            raise WorkspaceError("content must be a string", "INVALID_CONTENT")
        path = self.paths.resolve(file_path)
        display = self.paths.display(path)
        if path.exists() and not path.is_file():
            raise WorkspaceError(f'cannot write "{display}": not a regular file', "NOT_REGULAR_FILE")
        existed = path.is_file()
        _atomic_write(path, content, display)
        return display, "update" if existed else "create"

    def edit_text(self, file_path: str, old_string: str, new_string: str, replace_all: bool) -> str:
        display, path, data = self.read_bytes(file_path, "edit")
        raw = _decode_utf8(data, display, "edit")
        style = detect_line_endings(raw)
        edited = apply_literal_edit(normalize_lf(raw), old_string, new_string, replace_all, display)
        _atomic_write(path, restore_line_endings(edited, style), display)
        return display
