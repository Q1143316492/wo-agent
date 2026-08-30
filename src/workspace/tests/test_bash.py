"""bash 工具：假 runner 测契约；有本机 bash 时再测 spawn。"""

import asyncio
import json
import time
from pathlib import Path

import pytest

from compose import compose
from tools import RegistryToolExecutor
from workspace import BashCapability, WorkspaceCapability
from workspace.errors import WorkspaceError
from workspace.shell import BashResult, find_bash, format_bash_output, truncate_tail
from workspace.tools import make_bash_tool


class FakeRunner:
    def __init__(self, result: BashResult | None = None, error: Exception | None = None) -> None:
        self.result = result or BashResult(exit_code=0, output="ok\n", timed_out=False)
        self.error = error
        self.commands: list[tuple[str, Path, float]] = []
        self.last_cancel = None

    async def run(self, command: str, cwd: Path, timeout_s: float, cancel=None) -> BashResult:
        self.commands.append((command, cwd, timeout_s))
        self.last_cancel = cancel
        if self.error is not None:
            raise self.error
        return self.result


def test_truncate_tail_keeps_end():
    text, truncated = truncate_tail("a\nb\nc", max_lines=2, max_bytes=10_000)
    assert truncated is True
    assert text == "b\nc"


def test_format_includes_exit_and_timeout():
    result = BashResult(exit_code=124, output="partial", timed_out=True)
    text = format_bash_output(Path("/tmp/ws"), result, truncated=False)
    assert "exit: 124" in text
    assert "timed_out: true" in text
    assert "partial" in text


def test_format_includes_aborted():
    result = BashResult(exit_code=130, output="", timed_out=False, aborted=True)
    text = format_bash_output(Path("/tmp/ws"), result, truncated=False)
    assert "exit: 130" in text
    assert "aborted: true" in text


async def test_bash_tool_nonzero_exit_is_not_pipeline_error(tmp_path: Path):
    runner = FakeRunner(BashResult(exit_code=2, output="nope\n", timed_out=False))
    tools = RegistryToolExecutor()
    tools.register(make_bash_tool(tmp_path, runner))
    result = await tools.execute("bash", json.dumps({"command": "false"}))
    assert result.is_error is False
    assert "exit: 2" in result.content[0].text
    assert "nope" in result.content[0].text
    assert runner.commands[0][0] == "false"
    assert runner.commands[0][1] == tmp_path


async def test_empty_command_is_error(tmp_path: Path):
    tools = RegistryToolExecutor()
    tools.register(make_bash_tool(tmp_path, FakeRunner()))
    result = await tools.execute("bash", json.dumps({"command": "   "}))
    assert result.is_error is True


async def test_timeout_argument_forwarded(tmp_path: Path):
    runner = FakeRunner()
    tools = RegistryToolExecutor()
    tools.register(make_bash_tool(tmp_path, runner, default_timeout_s=30))
    await tools.execute("bash", json.dumps({"command": "echo x", "timeout": 5}))
    assert runner.commands[0][2] == 5


async def test_bash_tool_passes_cancel_event(tmp_path: Path):
    runner = FakeRunner()
    tools = RegistryToolExecutor()
    tools.register(make_bash_tool(tmp_path, runner))
    cancel = asyncio.Event()
    await tools.execute("bash", json.dumps({"command": "echo x"}), cancel=cancel)
    assert runner.last_cancel is cancel


def test_bash_capability_separate_from_files(tmp_path: Path):
    ctx = compose(WorkspaceCapability(tmp_path))
    assert {s.name for s in ctx.tools.schemas()} == {"read", "write", "edit"}
    ctx = compose(WorkspaceCapability(tmp_path), BashCapability(tmp_path, runner=FakeRunner()))
    assert {s.name for s in ctx.tools.schemas()} == {"read", "write", "edit", "bash"}
    assert "not sandboxed" in ctx.system_prompt.assemble()


def test_omitting_bash_has_no_bash_tool(tmp_path: Path):
    ctx = compose(WorkspaceCapability(tmp_path))
    assert "bash" not in {s.name for s in ctx.tools.schemas()}


def _has_bash() -> bool:
    try:
        find_bash()
        return True
    except WorkspaceError:
        return False


@pytest.mark.skipif(not _has_bash(), reason="no bash on this machine")
async def test_local_echo_runs_in_cwd(tmp_path: Path):
    from workspace.shell import LocalBashRunner

    runner = LocalBashRunner()
    result = await runner.run("echo hello && pwd", tmp_path, timeout_s=10)
    assert result.timed_out is False
    assert result.exit_code == 0
    assert "hello" in result.output


@pytest.mark.skipif(not _has_bash(), reason="no bash on this machine")
async def test_local_timeout(tmp_path: Path):
    from workspace.shell import LocalBashRunner

    runner = LocalBashRunner()
    result = await runner.run("sleep 8", tmp_path, timeout_s=0.3)
    assert result.timed_out is True
    assert result.exit_code == 124


@pytest.mark.skipif(not _has_bash(), reason="no bash on this machine")
async def test_local_abort_kills_sleep(tmp_path: Path):
    from workspace.shell import LocalBashRunner

    runner = LocalBashRunner()
    cancel = asyncio.Event()

    async def abort_soon():
        await asyncio.sleep(0.2)
        cancel.set()

    asyncio.create_task(abort_soon())
    started = time.monotonic()
    result = await runner.run("sleep 8", tmp_path, timeout_s=30, cancel=cancel)
    elapsed = time.monotonic() - started
    assert result.aborted is True
    assert result.timed_out is False
    assert result.exit_code == 130
    assert elapsed < 4


@pytest.mark.skipif(not _has_bash(), reason="no bash on this machine")
async def test_local_already_cancelled_does_not_run(tmp_path: Path):
    from workspace.shell import LocalBashRunner

    cancel = asyncio.Event()
    cancel.set()
    marker = tmp_path / "ran.txt"
    runner = LocalBashRunner()
    result = await runner.run("echo x > ran.txt", tmp_path, timeout_s=10, cancel=cancel)
    assert result.aborted is True
    assert result.exit_code == 130
    assert not marker.exists()
