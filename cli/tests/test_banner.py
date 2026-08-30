from __future__ import annotations

import pytest

from cli.tui.banner import _BLURB, render_banner
from cli.tui.icons import catalog, icon_ids, resolve
from cli.tui.icons.sprite import render_sprite
from cli.tui.icons.v1 import PALETTE, SPRITE


def test_v1_kept_as_backup_default_is_v2():
    assert icon_ids() == ("v1", "v2")
    assert resolve().id == "v2"
    assert catalog()["v1"].title == "银虎斑美短"
    assert catalog()["v2"].title == "银虎斑美短"


def test_unknown_icon_raises():
    with pytest.raises(ValueError, match="unknown icon"):
        resolve("nope")


def test_icon_from_env(monkeypatch):
    monkeypatch.setenv("WO_AGENT_ICON", "v1")
    assert resolve().id == "v1"


def test_v1_sprite():
    rows = SPRITE.splitlines()
    width = len(rows[0])
    assert all(len(row) == width for row in rows)
    used = set("".join(rows)) - set(". \n")
    assert used <= set(PALETTE)
    assert "t" in used
    assert "g" in used
    assert "p" not in used


def test_same_color_cell_is_full_block():
    plain = render_sprite("##\n##", {"#": "#c8ccd4"}).plain
    assert "█" in plain
    assert "▀" not in plain


def test_render_v1():
    plain = render_banner("v1").plain
    assert "█" in plain
    assert r"/\_/" not in plain
    assert plain.count("\n") >= 12
    assert "wo-agent" not in plain


def test_v2_sprite_is_smaller_than_v1():
    from cli.tui.icons.v2 import PALETTE as PALETTE2, SPRITE as SPRITE2

    rows = SPRITE2.splitlines()
    width = len(rows[0])
    assert all(len(row) == width for row in rows)
    used = set("".join(rows)) - set(". \n")
    assert used <= set(PALETTE2)
    assert "t" in used
    assert "g" in used
    assert width < len(SPRITE.splitlines()[0])
    assert len(rows) < len(SPRITE.splitlines())


def test_render_v2_shorter_than_v1():
    v1 = render_banner("v1").plain
    v2 = render_banner("v2").plain
    assert "█" in v2
    assert v2.count("\n") < v1.count("\n")
    assert "wo-agent" not in v2


def test_blurb_explains_the_tool():
    assert "wo-agent" in _BLURB
    assert "个人助理" in _BLURB
    assert "我是" in _BLURB
    assert "随时待命" in _BLURB
    assert "终于等到" not in _BLURB
    assert "尽管开口" not in _BLURB
    assert "以 / 开头" not in _BLURB
