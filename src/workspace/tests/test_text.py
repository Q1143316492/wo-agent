"""字面量 edit 与 UTF-8 存储。"""

from pathlib import Path

import pytest

from workspace.errors import WorkspaceError
from workspace.paths import WorkspacePaths
from workspace.text import WorkspaceStore, apply_literal_edit, normalize_lf


def test_unique_replace(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    store.write_text("a.txt", "hello world\n")
    store.edit_text("a.txt", "world", "there", replace_all=False)
    assert store.read_text("a.txt")[1] == "hello there\n"


def test_missing_old_string_does_not_change_file(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    store.write_text("a.txt", "keep\n")
    with pytest.raises(WorkspaceError) as caught:
        store.edit_text("a.txt", "absent", "x", replace_all=False)
    assert caught.value.code == "EDIT_NOT_FOUND"
    assert store.read_text("a.txt")[1] == "keep\n"


def test_ambiguous_without_replace_all(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    store.write_text("a.txt", "aa")
    with pytest.raises(WorkspaceError) as caught:
        store.edit_text("a.txt", "a", "b", replace_all=False)
    assert caught.value.code == "AMBIGUOUS_EDIT"
    assert store.read_text("a.txt")[1] == "aa"


def test_replace_all(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    store.write_text("a.txt", "aa")
    store.edit_text("a.txt", "a", "b", replace_all=True)
    assert store.read_text("a.txt")[1] == "bb"


def test_crlf_old_string_matches_crlf_file(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    (tmp_path / "a.txt").write_bytes(b"hello\r\nworld\r\n")
    store.edit_text("a.txt", "hello\r\nworld", "hello\r\nthere", replace_all=False)
    assert (tmp_path / "a.txt").read_bytes() == b"hello\r\nthere\r\n"


def test_lf_old_string_matches_crlf_file(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    (tmp_path / "a.txt").write_bytes(b"hello\r\nworld\r\n")
    store.edit_text("a.txt", "hello\nworld", "hello\nthere", replace_all=False)
    assert (tmp_path / "a.txt").read_bytes() == b"hello\r\nthere\r\n"


def test_edit_restores_crlf(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    (tmp_path / "a.txt").write_bytes(b"one\r\ntwo\r\n")
    store.edit_text("a.txt", "one", "ONE", replace_all=False)
    assert (tmp_path / "a.txt").read_bytes() == b"ONE\r\ntwo\r\n"


def test_write_creates_parent_directories(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    display, operation = store.write_text("nested/dir/a.txt", "x")
    assert operation == "create"
    assert display == "nested/dir/a.txt"
    assert (tmp_path / "nested" / "dir" / "a.txt").read_text(encoding="utf-8") == "x"


def test_write_overwrite(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    store.write_text("a.txt", "old")
    _, operation = store.write_text("a.txt", "new")
    assert operation == "update"
    assert store.read_text("a.txt")[1] == "new"


def test_write_empty_content(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    store.write_text("a.txt", "")
    assert store.read_text("a.txt")[1] == ""


def test_binary_rejected(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    (tmp_path / "a.bin").write_bytes(b"a\x00b")
    with pytest.raises(WorkspaceError) as caught:
        store.read_text("a.bin")
    assert caught.value.code == "NOT_TEXT"


def test_directory_is_not_a_file(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    (tmp_path / "dir").mkdir()
    with pytest.raises(WorkspaceError) as caught:
        store.read_text("dir")
    assert caught.value.code == "NOT_REGULAR_FILE"


def test_missing_file(tmp_path: Path):
    store = WorkspaceStore(WorkspacePaths(tmp_path))
    with pytest.raises(WorkspaceError) as caught:
        store.read_text("nope.txt")
    assert caught.value.code == "NOT_FOUND"


def test_apply_literal_edit_empty_old():
    with pytest.raises(WorkspaceError):
        apply_literal_edit("abc", "", "x", False, "a.txt")


def test_normalize_lf_leaves_lone_cr():
    assert normalize_lf("a\rb\r\nc") == "a\rb\nc"
