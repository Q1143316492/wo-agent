"""SearchCapability：假 runner 测契约；不调用本机 rg。"""

import json
from pathlib import Path

from compose import compose
from tools import RegistryToolExecutor
from workspace.paths import WorkspacePaths
from workspace.search import SearchResult, format_search_output, glob_argv, grep_argv, resolve_rg
from workspace.tools import make_glob_tool, make_grep_tool


class FakeSearchRunner:
    def __init__(self, result: SearchResult | None = None) -> None:
        self.result = result or SearchResult(exit_code=0, output="src/a.py:1:hit\n")
        self.calls: list[tuple[list[str], Path, float]] = []
        self.last_cancel = None

    async def run(self, argv: list[str], cwd: Path, timeout_s: float, cancel=None) -> SearchResult:
        self.calls.append((list(argv), cwd, timeout_s))
        self.last_cancel = cancel
        return self.result


def _search_executor(root: Path, runner: FakeSearchRunner) -> RegistryToolExecutor:
    paths = WorkspacePaths(root)
    tools = RegistryToolExecutor()
    tools.register(make_grep_tool(paths, runner))
    tools.register(make_glob_tool(paths, runner))
    return tools


def test_resolve_prefers_explicit(tmp_path: Path):
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "rg.exe").write_text("no", encoding="utf-8")
    explicit = tmp_path / "mine" / "rg"
    explicit.parent.mkdir()
    explicit.write_text("yes", encoding="utf-8")
    found = resolve_rg(explicit=str(explicit), vendor_dir=vendor)
    assert found == explicit.resolve()


def test_resolve_vendor_then_none(tmp_path: Path, monkeypatch):
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    binary = vendor / "rg"
    binary.write_text("v", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert resolve_rg(explicit=None, vendor_dir=vendor) == binary.resolve()
    assert resolve_rg(explicit=None, vendor_dir=tmp_path / "missing") is None


def test_grep_argv_puts_pattern_after_double_dash():
    assert grep_argv(pattern="foo", path="src") == [
        "--color",
        "never",
        "-n",
        "--",
        "foo",
        "src",
    ]
    assert "-g" in grep_argv(pattern="foo", path=".", glob="*.py")
    assert "-i" in grep_argv(pattern="foo", path=".", case_insensitive=True)


def test_format_includes_aborted():
    text = format_search_output(SearchResult(exit_code=130, output="", aborted=True), truncated=False)
    assert "exit: 130" in text
    assert "aborted: true" in text


def test_glob_argv_uses_files_and_g():
    assert glob_argv(pattern="**/*.py", path=".") == [
        "--files",
        "--color",
        "never",
        "-g",
        "**/*.py",
        ".",
    ]


async def test_grep_passes_cancel_event(tmp_path: Path):
    import asyncio

    runner = FakeSearchRunner()
    tools = _search_executor(tmp_path, runner)
    cancel = asyncio.Event()
    await tools.execute("grep", json.dumps({"pattern": "foo"}), cancel=cancel)
    assert runner.last_cancel is cancel


async def test_grep_forwards_argv_and_is_not_pipeline_error(tmp_path: Path):
    runner = FakeSearchRunner(SearchResult(exit_code=1, output=""))
    tools = _search_executor(tmp_path, runner)
    result = await tools.execute("grep", json.dumps({"pattern": "foo"}))
    assert result.is_error is False
    assert runner.calls[0][0] == ["--color", "never", "-n", "--", "foo", "."]
    assert runner.calls[0][1] == tmp_path.resolve()


async def test_grep_path_outside_root_does_not_spawn(tmp_path: Path):
    runner = FakeSearchRunner()
    tools = _search_executor(tmp_path, runner)
    result = await tools.execute("grep", json.dumps({"pattern": "foo", "path": "../secret"}))
    assert result.is_error is True
    assert "outside the workspace root" in result.content[0].text
    assert runner.calls == []


async def test_glob_forwards_files_argv(tmp_path: Path):
    runner = FakeSearchRunner(SearchResult(exit_code=0, output="a.py\n"))
    tools = _search_executor(tmp_path, runner)
    result = await tools.execute("glob", json.dumps({"pattern": "*.py"}))
    assert result.is_error is False
    assert "a.py" in result.content[0].text
    assert runner.calls[0][0] == ["--files", "--color", "never", "-g", "*.py", "."]


def test_search_capability_registers_two_tools(tmp_path: Path):
    from workspace import SearchCapability, WorkspaceCapability

    ctx = compose(
        WorkspaceCapability(tmp_path),
        SearchCapability(tmp_path, runner=FakeSearchRunner()),
    )
    assert {s.name for s in ctx.tools.schemas()} == {"read", "write", "edit", "grep", "glob"}


def test_omitting_search_has_no_grep(tmp_path: Path):
    from workspace import WorkspaceCapability

    ctx = compose(WorkspaceCapability(tmp_path))
    assert {s.name for s in ctx.tools.schemas()} == {"read", "write", "edit"}
