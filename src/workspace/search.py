"""本机 ripgrep：路径解析、argv、起进程。匹配算法在 rg 里，这里不起搜索。"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .errors import WorkspaceError
from .shell import MAX_OUTPUT_BYTES, MAX_OUTPUT_LINES, _reap_subprocess, await_proc


@dataclass(frozen=True)
class SearchResult:
    exit_code: int
    output: str
    aborted: bool = False


class SearchRunner(Protocol):
    async def run(
        self,
        argv: list[str],
        cwd: Path,
        timeout_s: float,
        cancel: asyncio.Event | None = None,
    ) -> SearchResult: ...


def resolve_rg(*, explicit: str | None = None, vendor_dir: str | Path | None = None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return path.resolve()
    if vendor_dir is not None:
        directory = Path(vendor_dir)
        if directory.is_dir():
            for name in ("rg.exe", "rg"):
                candidate = directory / name
                if candidate.is_file():
                    return candidate.resolve()
    which = shutil.which("rg")
    if which:
        return Path(which).resolve()
    return None


def grep_argv(
    *,
    pattern: str,
    path: str,
    glob: str | None = None,
    case_insensitive: bool = False,
) -> list[str]:
    argv = ["--color", "never", "-n"]
    if case_insensitive:
        argv.append("-i")
    if glob:
        argv.extend(["-g", glob])
    argv.extend(["--", pattern, path])
    return argv


def glob_argv(*, pattern: str, path: str) -> list[str]:
    return ["--files", "--color", "never", "-g", pattern, path]


def format_search_output(result: SearchResult, truncated: bool) -> str:
    header = [f"exit: {result.exit_code}"]
    if result.aborted:
        header.append("aborted: true")
    body = result.output
    if truncated:
        note = (
            f"(Output truncated to last {MAX_OUTPUT_LINES} lines "
            f"or {MAX_OUTPUT_BYTES} bytes.)"
        )
        body = (body + "\n\n" + note) if body else note
    if body:
        return "\n".join(header) + "\n\n" + body
    return "\n".join(header)


class LocalRipgrepRunner:
    def __init__(self, rg_path: str | Path) -> None:
        self._rg = Path(rg_path)

    async def run(
        self,
        argv: list[str],
        cwd: Path,
        timeout_s: float,
        cancel: asyncio.Event | None = None,
    ) -> SearchResult:
        if cancel is not None and cancel.is_set():
            return SearchResult(exit_code=130, output="", aborted=True)
        if not self._rg.is_file():
            raise WorkspaceError(f"rg not found: {self._rg}", "RG_NOT_FOUND")
        kwargs: dict = {}
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        elif sys.platform != "win32":
            kwargs["start_new_session"] = True
        proc = await asyncio.create_subprocess_exec(
            str(self._rg),
            *argv,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            **kwargs,
        )
        stdout = b""
        timed_out = False
        aborted = False
        try:
            stdout, timed_out, aborted = await await_proc(proc, timeout_s, cancel)
        finally:
            await _reap_subprocess(proc)
        text = stdout.decode("utf-8", errors="replace")
        if aborted:
            return SearchResult(exit_code=130, output=text, aborted=True)
        if timed_out:
            return SearchResult(exit_code=124, output=text)
        code = proc.returncode if proc.returncode is not None else 1
        return SearchResult(exit_code=code, output=text)


__all__ = [
    "LocalRipgrepRunner",
    "SearchResult",
    "SearchRunner",
    "format_search_output",
    "glob_argv",
    "grep_argv",
    "resolve_rg",
]
