"""启动画面：左边 icon，右边说明。猫不随窗口变窄而折行。"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from cli.tui.icons import resolve

_BLURB = """wo-agent

我是你的个人助理。随时待命。
读写这个目录、执行命令，说一声即可。
"""


def render_banner(icon_id: str | None = None) -> Text:
    return resolve(icon_id).render()


class Banner(Horizontal):
    can_focus = False

    DEFAULT_CSS = """
    Banner {
        height: auto;
        margin: 1 0 0 0;
        background: transparent;
        overflow-x: hidden;
    }
    Banner #mark {
        height: auto;
        text-wrap: nowrap;
        overflow: hidden;
        background: transparent;
    }
    Banner #blurb {
        width: 1fr;
        min-width: 16;
        height: auto;
        color: $text-muted;
        padding: 0 2 0 3;
        background: transparent;
    }
    """

    def __init__(self, icon_id: str | None = None) -> None:
        super().__init__()
        icon = resolve(icon_id)
        self.icon_id = icon.id
        mark = icon.render()
        self._mark = Static(mark, id="mark", markup=False)
        self._mark.can_focus = False
        self._blurb = Static(_BLURB.rstrip(), id="blurb", markup=False)
        self._blurb.can_focus = False
        width = max((len(line) for line in mark.plain.splitlines()), default=1)
        self._mark.styles.width = width
        self._mark.styles.min_width = width

    def compose(self) -> ComposeResult:
        yield self._mark
        yield self._blurb
