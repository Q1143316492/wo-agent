"""工具经执行管线：成功、越界、唯一匹配失败。"""

import json
from pathlib import Path

from tools import RegistryToolExecutor
from workspace.paths import WorkspacePaths
from workspace.text import WorkspaceStore
from workspace.tools import make_edit_tool, make_read_tool, make_write_tool


def _executor(root: Path) -> RegistryToolExecutor:
    store = WorkspaceStore(WorkspacePaths(root))
    tools = RegistryToolExecutor()
    tools.register(make_read_tool(store))
    tools.register(make_write_tool(store))
    tools.register(make_edit_tool(store))
    return tools


async def test_write_read_edit_roundtrip(tmp_path: Path):
    tools = _executor(tmp_path)
    written = await tools.execute("write", json.dumps({"file_path": "a.txt", "content": "hello world\n"}))
    assert written.is_error is False
    assert "Created file" in written.content[0].text

    read = await tools.execute("read", json.dumps({"file_path": "a.txt"}))
    assert "1: hello world" in read.content[0].text

    edited = await tools.execute(
        "edit",
        json.dumps({"file_path": "a.txt", "old_string": "world", "new_string": "there"}),
    )
    assert edited.is_error is False
    assert "updated successfully" in edited.content[0].text
    again = await tools.execute("read", json.dumps({"file_path": "a.txt"}))
    assert "hello there" in again.content[0].text


async def test_edit_not_found_is_error(tmp_path: Path):
    tools = _executor(tmp_path)
    await tools.execute("write", json.dumps({"file_path": "a.txt", "content": "keep\n"}))
    result = await tools.execute(
        "edit",
        json.dumps({"file_path": "a.txt", "old_string": "missing\n", "new_string": "x\n"}),
    )
    assert result.is_error is True
    assert "was not found" in result.content[0].text
    kept = await tools.execute("read", json.dumps({"file_path": "a.txt"}))
    assert "1: keep" in kept.content[0].text


async def test_path_escape_is_error(tmp_path: Path):
    tools = _executor(tmp_path)
    result = await tools.execute("read", json.dumps({"file_path": "../secret.txt"}))
    assert result.is_error is True
    assert "outside the workspace root" in result.content[0].text


async def test_replace_all_wording(tmp_path: Path):
    tools = _executor(tmp_path)
    await tools.execute("write", json.dumps({"file_path": "a.txt", "content": "aa"}))
    result = await tools.execute(
        "edit",
        json.dumps({"file_path": "a.txt", "old_string": "a", "new_string": "b", "replace_all": True}),
    )
    assert result.is_error is False
    assert "All occurrences" in result.content[0].text
