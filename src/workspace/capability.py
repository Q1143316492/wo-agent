"""工作区能力：文件三件套与可选的本机 ``bash``。

循环不知道工作区。没把对应 Capability 传进 ``compose()`` 就没有那些刀。
文件围栏在 ``WorkspaceStore``；``bash`` 的 cwd 钉在同一根上，但围栏管不住命令。
"""

from __future__ import annotations

from pathlib import Path

from system_prompt import PromptSection

from .paths import WorkspacePaths
from .shell import DEFAULT_TIMEOUT_S, BashRunner, LocalBashRunner
from .text import WorkspaceStore
from .tools import make_bash_tool, make_edit_tool, make_read_tool, make_write_tool


def _file_guidance(root: Path) -> str:
    display = root.as_posix()
    return (
        f"Workspace root: {display}. "
        "Use read, write, and edit for UTF-8 text files under this root. "
        "Paths are relative to the root unless they are an absolute path inside it. "
        "Use read — not bash — to inspect file contents; results include line numbers. "
        "Use write to create a file or fully replace its contents; prefer edit for targeted changes. "
        "edit replaces literal old_string with new_string; by default old_string must appear exactly once. "
        "If old_string appears multiple times, provide a more specific old_string or set replace_all to true. "
        "Paths outside the root are rejected by read/write/edit."
    )


def _bash_guidance(cwd: Path) -> str:
    display = cwd.as_posix()
    return (
        f"Use bash to run commands with cwd {display}. "
        "bash is not sandboxed and can read or write paths outside the workspace root. "
        "Prefer read/write/edit for file changes. Non-zero exit codes are returned in the tool result; "
        "the tool itself still succeeds."
    )


class WorkspaceCapability:
    def __init__(self, root: str | Path) -> None:
        self._store = WorkspaceStore(WorkspacePaths(root))

    @property
    def root(self) -> Path:
        return self._store.paths.root

    def mount(self, ctx) -> None:
        ctx.tools.register(make_read_tool(self._store))
        ctx.tools.register(make_write_tool(self._store))
        ctx.tools.register(make_edit_tool(self._store))
        ctx.system_prompt.section(
            PromptSection(name="workspace:tools", order=110, text=_file_guidance(self._store.paths.root))
        )


class BashCapability:
    """本机 bash。``cwd`` 应与工作区根相同；可单独省略（例如 Unity 只用 execPython）。"""

    def __init__(
        self,
        cwd: str | Path,
        runner: BashRunner | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        shell_path: str | None = None,
    ) -> None:
        resolved = Path(cwd).expanduser().resolve()
        if not resolved.is_dir():
            resolved.mkdir(parents=True, exist_ok=True)
        self._cwd = resolved
        self._runner = runner if runner is not None else LocalBashRunner(shell_path)
        self._timeout_s = timeout_s

    @property
    def cwd(self) -> Path:
        return self._cwd

    def mount(self, ctx) -> None:
        ctx.tools.register(make_bash_tool(self._cwd, self._runner, self._timeout_s))
        ctx.system_prompt.section(
            PromptSection(name="workspace:bash", order=111, text=_bash_guidance(self._cwd))
        )
