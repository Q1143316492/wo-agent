from __future__ import annotations

import pytest

from cli.tui.banner import _BLURB, render_banner
from cli.tui.icons import catalog, icon_ids, resolve
from cli.tui.icons.sprite import render_sprite
from cli.tui.icons.v1 import PALETTE, SPRITE


def test_v1_is_the_only_icon():
    assert icon_ids() == ("v1",)
    assert resolve().id == "v1"
    assert catalog()["v1"].title == "银虎斑美短"


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


def test_blurb_explains_the_tool():
    assert "wo-agent" in _BLURB
    assert "个人助理" in _BLURB
    assert "/help" in _BLURB
