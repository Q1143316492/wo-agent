from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

textual = pytest.importorskip("textual")

from cli.boot import Booted
from cli.tui.app import WoCli
from cli.tui.banner import Banner
from cli.tui.widgets import CancelLine, MetaLine, NoteLine, QueueStrip, ToolBlock, UserLine
from session import Session


def _boot_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("UTAGENT_API_KEY", raising=False)
    monkeypatch.setenv("WO_AGENT_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("WO_AGENT_SESSIONS", str(tmp_path / "sessions"))
    (tmp_path / "ws").mkdir()


class _FakeStore:
    def save(self, session) -> None:
        self.saved = session


class _FakeAgent:
    def __init__(self) -> None:
        self.followups: list[str] = []
        self.enqueued: list[str] = []
        self.cancels: list[tuple[str, bool]] = []
        self._queue: list[tuple[str, str]] = []
        self._ids = 0
        self._gate = asyncio.Event()
        self.status = "idle"
        self.session = Session()

    async def followup(self, text: str) -> None:
        self.followups.append(text)
        self.status = "running"
        await self._gate.wait()
        self.status = "idle"

    def enqueue(self, text: str) -> None:
        self._ids += 1
        self._queue.append((str(self._ids), text))
        self.enqueued.append(text)

    def queued(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._queue)

    def take_back(self) -> str | None:
        if not self._queue:
            return None
        _, text = self._queue.pop()
        return text

    def cancel(self, cause: str, *, keep_inbox: bool = False) -> None:
        self.cancels.append((cause, keep_inbox))
        if not keep_inbox:
            self._queue.clear()
        self._gate.set()

    async def when_idle(self) -> None:
        await self._gate.wait()


def _patch_boot(monkeypatch, tmp_path, agent: _FakeAgent) -> None:
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)

    def fake_boot(on_chunk, resume=None, on_tool_start=None, on_tool_end=None):
        return Booted(
            ctx=SimpleNamespace(tools=SimpleNamespace(schemas=lambda: [])),
            session=agent.session,
            agent=agent,
            store=_FakeStore(),
            workspace=ws,
            sessions_dir=tmp_path / "sessions",
        )

    monkeypatch.setattr("cli.tui.app.boot", fake_boot)


@pytest.mark.asyncio
async def test_mount_shows_session(tmp_path, monkeypatch):
    _boot_env(tmp_path, monkeypatch)
    app = WoCli()
    async with app.run_test() as _pilot:
        assert app._booted is not None
        names = {s.name for s in app._booted.ctx.tools.schemas()}
        assert "read" in names
        assert "bash" in names
        status = str(app.query_one("#status").content)
        assert "idle" in status
        assert "in=0" in status
        assert "out=0" in status
        composer = app.query_one("#composer")
        assert composer.placeholder
        meta = app.query_one(MetaLine)
        assert "ws" in str(meta.content)
        banner = app.query_one(Banner)
        blurb = str(banner.query_one("#blurb").content)
        assert "wo-agent" in blurb
        assert "个人助理" in blurb
        assert composer.has_focus


@pytest.mark.asyncio
async def test_help_and_clear_keep_focus(tmp_path, monkeypatch):
    _boot_env(tmp_path, monkeypatch)
    app = WoCli()
    async with app.run_test() as pilot:
        composer = app.query_one("#composer")
        composer.value = "/help"
        await pilot.press("enter")
        note = app.query_one(NoteLine)
        assert "/clear" in str(note.content)
        assert composer.has_focus

        composer.value = "/clear"
        await pilot.press("enter")
        children = list(app.query_one("#thread").children)
        assert len(children) == 2
        assert isinstance(children[0], Banner)
        assert isinstance(children[1], MetaLine)
        assert list(app.query(NoteLine)) == []
        assert composer.has_focus


@pytest.mark.asyncio
async def test_slash_menu_filters_and_tab_completes(tmp_path, monkeypatch):
    _boot_env(tmp_path, monkeypatch)
    app = WoCli()
    async with app.run_test() as pilot:
        composer = app.query_one("#composer")
        await pilot.press("/")
        menu = app.query_one("#slash")
        assert menu.display
        assert menu.option_count == 6
        await pilot.press("c")
        assert menu.option_count == 1
        assert menu.highlighted_option is not None
        assert menu.highlighted_option.id == "clear"
        await pilot.press("tab")
        assert composer.value == "/clear "
        assert not menu.display
        assert composer.has_focus


@pytest.mark.asyncio
async def test_enter_while_busy_enqueues_and_escape_keeps_queue(tmp_path, monkeypatch):
    agent = _FakeAgent()
    _patch_boot(monkeypatch, tmp_path, agent)
    app = WoCli()
    async with app.run_test() as pilot:
        composer = app.query_one("#composer")
        composer.value = "first"
        await pilot.press("enter")
        await pilot.pause()
        assert app._busy
        assert "thinking" in str(app.query_one("#status").content)
        assert agent.followups == ["first"]
        assert list(app.query(UserLine))

        composer.value = "later"
        await pilot.press("enter")
        await pilot.pause()
        assert agent.enqueued == ["later"]
        assert agent.followups == ["first"]
        assert app._busy
        user_lines = [str(line.content) for line in app.query(UserLine)]
        assert any("first" in text for text in user_lines)
        assert not any("later" in text for text in user_lines)
        queue = app.query_one("#queue", QueueStrip)
        assert queue.display
        assert "later" in str(queue.content)

        await pilot.press("escape")
        await pilot.pause()
        assert agent.cancels == [("user", True)]
        assert agent.queued() == (("1", "later"),)
        assert app.query_one(CancelLine)

        composer.value = ""
        composer.cursor_position = 0
        await pilot.press("up")
        await pilot.pause()
        assert composer.value == "later"
        assert agent.queued() == ()
        assert not queue.display


@pytest.mark.asyncio
async def test_name_command_saves_title(tmp_path, monkeypatch):
    _boot_env(tmp_path, monkeypatch)
    app = WoCli()
    async with app.run_test() as pilot:
        composer = app.query_one("#composer")
        composer.value = "/name 登录页"
        await pilot.press("enter")
        await pilot.pause()
        assert app._booted is not None
        assert app._booted.session.title == "登录页"
        loaded = app._booted.store.load(app._booted.session.id)
        assert loaded is not None
        assert loaded.title == "登录页"


@pytest.mark.asyncio
async def test_tool_blocks_show_command_and_toggle(tmp_path, monkeypatch):
    agent = _FakeAgent()
    _patch_boot(monkeypatch, tmp_path, agent)
    app = WoCli()
    async with app.run_test() as _pilot:
        app._busy = True
        app._apply_tool_start("bash", json.dumps({"command": "echo a"}))
        assert "running bash" in str(app.query_one("#status").content)
        app._apply_tool_end("bash", "exit: 0\na", False)
        app._apply_tool_start("bash", json.dumps({"command": "echo b"}))
        app._apply_tool_end("bash", "exit: 0\n" + "\n".join(str(i) for i in range(12)), False)
        blocks = list(app.query(ToolBlock))
        assert len(blocks) == 2
        assert "echo a" in str(blocks[0].content)
        assert "echo b" in str(blocks[1].content)
        collapsed = str(blocks[1].content)
        assert collapsed.splitlines()[-1] == "11"
        app.action_toggle_tool()
        expanded = str(blocks[1].content)
        assert expanded.splitlines()[2] == "0"
        assert "thinking" in str(app.query_one("#status").content)
