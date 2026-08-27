"""根目录围栏：相对路径相对根解析；解析后必须仍在根下。

对齐 dsh 沙箱的 containment 意图，不做升权、不做按调用的 sandbox 模式。
``Path.resolve()`` 会跟 symlink，因此根内的外指链接会落到根外并被拒绝。
Windows 用 ``normcase`` 比较，避免盘符大小写把合法路径判出界。
"""

from __future__ import annotations

import os
from pathlib import Path

from .errors import WorkspaceError


def _under_root(resolved: Path, root: Path) -> bool:
    target = os.path.normcase(str(resolved))
    base = os.path.normcase(str(root))
    if target == base:
        return True
    prefix = base if base.endswith(os.sep) else base + os.sep
    return target.startswith(prefix)


class WorkspacePaths:
    """一个围栏根。所有工具路径都经 ``resolve``。"""

    def __init__(self, root: str | Path) -> None:
        resolved = Path(root).expanduser().resolve()
        if not resolved.exists():
            resolved.mkdir(parents=True, exist_ok=True)
        if not resolved.is_dir():
            raise WorkspaceError(f"workspace root is not a directory: {resolved}", "NOT_A_DIRECTORY")
        self.root = resolved

    def resolve(self, file_path: str) -> Path:
        raw = file_path.strip() if isinstance(file_path, str) else ""
        if not raw:
            raise WorkspaceError("file_path must be a non-empty string", "INVALID_PATH")
        if "\x00" in raw:
            raise WorkspaceError("file_path must be a non-empty string", "INVALID_PATH")
        candidate = Path(raw)
        resolved = candidate.resolve() if candidate.is_absolute() else (self.root / candidate).resolve()
        if not _under_root(resolved, self.root):
            raise WorkspaceError(
                f"path is outside the workspace root: {raw}",
                "PATH_OUTSIDE_ROOT",
            )
        return resolved

    def display(self, resolved: Path) -> str:
        """给模型看的相对 posix 路径；恰好是根时为 ``.``。"""
        relative = os.path.relpath(str(resolved), str(self.root))
        if relative in (".", ""):
            return "."
        return Path(relative).as_posix()
