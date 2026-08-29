from __future__ import annotations

import pytest

textual = pytest.importorskip("textual")

from cli.tui.app import WoCli
from cli.tui.banner import Banner
from cli.tui.widgets import MetaLine, NoteLine


def _boot_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("UTAGENT_API_KEY", raising=False)
    monkeypatch.setenv("WO_AGENT_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("WO_AGENT_SESSIONS", str(tmp_path / "sessions"))
    (tmp_path / "ws").mkdir()


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
        assert menu.option_count == 3
        await pilot.press("c")
        assert menu.option_count == 1
        assert menu.highlighted_option is not None
        assert menu.highlighted_option.id == "clear"
        await pilot.press("tab")
        assert composer.value == "/clear "
        assert not menu.display
        assert composer.has_focus
