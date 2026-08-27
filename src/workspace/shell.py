"""本机 bash：在工作区根 ``spawn`` 真 shell。

对齐 pi 的 ``bash`` 工具，不是 dsh 沙箱产品。无审批、无升权。文件围栏
管不住这里——命令可以读到根外。Windows 只找 bash（Git Bash 等），不改成 cmd。
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import WorkspaceError

DEFAULT_TIMEOUT_S = 30
MAX_TIMEOUT_S = 300
MAX_OUTPUT_LINES = 2000
MAX_OUTPUT_BYTES = 50 * 1024


@dataclass(frozen=True)
class BashResult:
    exit_code: int
    output: str
    timed_out: bool


class BashRunner(Protocol):
    async def run(self, command: str, cwd: Path, timeout_s: float) -> BashResult: ...


def find_bash(shell_path: str | None = None) -> Path:
    """解析要执行的 bash。找不到就说明原因，不回退到 cmd。"""
    if shell_path:
        path = Path(shell_path)
        if path.is_file():
            return path
        raise WorkspaceError(f"bash not found: {shell_path}", "BASH_NOT_FOUND")

    if sys.platform == "win32":
        candidates: list[Path] = []
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(env_name)
            if root:
                candidates.append(Path(root) / "Git" / "bin" / "bash.exe")
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        which = _which("bash.exe")
        if which is not None:
            return which
        searched = "\n".join(f"  {p}" for p in candidates) or "  (no Program Files)"
        raise WorkspaceError(
            "No bash shell found. Install Git for Windows, add bash.exe to PATH, "
            f"or pass shell_path. Searched:\n{searched}",
            "BASH_NOT_FOUND",
        )

    unix = Path("/bin/bash")
    if unix.is_file():
        return unix
    which = _which("bash")
    if which is not None:
        return which
    sh = Path("/bin/sh")
    if sh.is_file():
        return sh
    raise WorkspaceError("No bash shell found on this system.", "BASH_NOT_FOUND")


def _which(name: str) -> Path | None:
    found = os.environ.get("PATH", "")
    for directory in found.split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / name
        if candidate.is_file():
            return candidate
    return None


def truncate_tail(text: str, max_lines: int = MAX_OUTPUT_LINES, max_bytes: int = MAX_OUTPUT_BYTES) -> tuple[str, bool]:
    if not text:
        return text, False
    total_bytes = len(text.encode("utf-8"))
    lines = text.split("\n")
    if len(lines) <= max_lines and total_bytes <= max_bytes:
        return text, False
    selected: list[str] = []
    size = 0
    for line in reversed(lines):
        extra = len(line.encode("utf-8")) + (1 if selected else 0)
        if selected and (len(selected) >= max_lines or size + extra > max_bytes):
            break
        if not selected and extra > max_bytes:
            selected.append(line[-max_bytes:] if max_bytes else "")
            break
        selected.append(line)
        size += extra
    selected.reverse()
    return "\n".join(selected), True


def format_bash_output(cwd: Path, result: BashResult, truncated: bool) -> str:
    display = cwd.as_posix()
    header = [f"exit: {result.exit_code}", f"cwd: {display}"]
    if result.timed_out:
        header.append("timed_out: true")
    body = result.output
    if truncated:
        body = (body + "\n\n(Output truncated to last "
                f"{MAX_OUTPUT_LINES} lines or {MAX_OUTPUT_BYTES} bytes.)") if body else (
            f"(Output truncated to last {MAX_OUTPUT_LINES} lines or {MAX_OUTPUT_BYTES} bytes.)"
        )
    if body:
        return "\n".join(header) + "\n\n" + body
    return "\n".join(header)


class LocalBashRunner:
    def __init__(self, shell_path: str | None = None) -> None:
        self._shell_path = shell_path
        self._bash: Path | None = None

    def bash(self) -> Path:
        if self._bash is None:
            self._bash = find_bash(self._shell_path)
        return self._bash

    async def run(self, command: str, cwd: Path, timeout_s: float) -> BashResult:
        bash = self.bash()
        kwargs: dict = {}
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = await asyncio.create_subprocess_exec(
            str(bash),
            "-c",
            command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            **kwargs,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            leftover = b""
            try:
                leftover, _ = await asyncio.wait_for(proc.communicate(), timeout=2)
            except (TimeoutError, Exception):
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1)
                except (TimeoutError, Exception):
                    pass
            text = leftover.decode("utf-8", errors="replace")
            return BashResult(exit_code=124, output=text, timed_out=True)
        text = stdout.decode("utf-8", errors="replace")
        code = proc.returncode if proc.returncode is not None else 1
        return BashResult(exit_code=code, output=text, timed_out=False)
