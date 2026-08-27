"""WorkspacePaths：相对根解析；越界拒绝。"""

import os
from pathlib import Path

import pytest

from workspace.errors import WorkspaceError
from workspace.paths import WorkspacePaths


def test_relative_path_stays_under_root(tmp_path: Path):
    paths = WorkspacePaths(tmp_path)
    resolved = paths.resolve("notes/hello.txt")
    assert resolved == (tmp_path / "notes" / "hello.txt").resolve()
    assert paths.display(resolved) == "notes/hello.txt"


def test_parent_escape_is_rejected(tmp_path: Path):
    paths = WorkspacePaths(tmp_path)
    with pytest.raises(WorkspaceError) as caught:
        paths.resolve("../secret.txt")
    assert caught.value.code == "PATH_OUTSIDE_ROOT"


def test_absolute_inside_root_is_allowed(tmp_path: Path):
    paths = WorkspacePaths(tmp_path)
    target = tmp_path / "inside.txt"
    resolved = paths.resolve(str(target))
    assert resolved == target.resolve()
    assert paths.display(resolved) == "inside.txt"


def test_absolute_outside_root_is_rejected(tmp_path: Path):
    paths = WorkspacePaths(tmp_path)
    outsider = tmp_path.parent / "outside.txt"
    with pytest.raises(WorkspaceError) as caught:
        paths.resolve(str(outsider))
    assert caught.value.code == "PATH_OUTSIDE_ROOT"


def test_empty_path_rejected(tmp_path: Path):
    paths = WorkspacePaths(tmp_path)
    with pytest.raises(WorkspaceError) as caught:
        paths.resolve("   ")
    assert caught.value.code == "INVALID_PATH"


def test_dotdot_in_middle_cannot_leave_root(tmp_path: Path):
    paths = WorkspacePaths(tmp_path)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    resolved = paths.resolve("a/b/../c.txt")
    assert paths.display(resolved) == "a/c.txt"


def test_symlink_escaping_root_is_rejected(tmp_path: Path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("nope", encoding="utf-8")
    link = root / "leak"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("symlink not permitted")
    paths = WorkspacePaths(root)
    with pytest.raises(WorkspaceError) as caught:
        paths.resolve("leak/secret.txt")
    assert caught.value.code == "PATH_OUTSIDE_ROOT"
