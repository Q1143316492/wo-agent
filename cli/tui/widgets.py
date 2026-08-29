"""对话里的消息块。只负责长什么样，不碰循环、不碰命令表。"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static


class Thread(VerticalScroll, can_focus=False):
    """对话区。不抢输入焦点；滚轮仍可滚动。"""

    DEFAULT_CSS = """
    Thread {
        height: 1fr;
        padding: 1 2 0 2;
        background: $background;
        scrollbar-gutter: stable;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
        scrollbar-background: $background;
        scrollbar-color: $foreground 22%;
        scrollbar-color-hover: $foreground 40%;
        scrollbar-color-active: $foreground 50%;
    }
    """


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        color: $text-muted;
        padding: 0 2;
        background: $background;
    }
    """


class MetaLine(Static):
    DEFAULT_CSS = """
    MetaLine {
        height: auto;
        color: $text-muted;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, text: str) -> None:
        super().__init__(text, markup=False)


class NoteLine(Static):
    """命令回执（/help、未知命令）。"""

    DEFAULT_CSS = """
    NoteLine {
        height: auto;
        color: $text-muted;
        margin: 0 0 1 1;
    }
    """

    def __init__(self, text: str) -> None:
        super().__init__(text, markup=False)


class UserLine(Static):
    DEFAULT_CSS = """
    UserLine {
        height: auto;
        color: $foreground;
        text-style: bold;
        margin: 1 0 1 0;
    }
    """

    def __init__(self, text: str) -> None:
        super().__init__(f"❯  {text}", markup=False)


class ThinkLine(Static, can_focus=False):
    DEFAULT_CSS = """
    ThinkLine {
        height: auto;
        max-height: 8;
        overflow-y: auto;
        color: $text-muted;
        text-style: italic;
        border-left: wide $foreground 20%;
        padding: 0 1;
        margin: 0 0 1 1;
        scrollbar-size-vertical: 1;
        scrollbar-background: $background;
        scrollbar-color: $foreground 22%;
    }
    """

    def __init__(self) -> None:
        super().__init__("", markup=False)

    def set_text(self, text: str) -> None:
        self.update(text.strip())


class ToolLine(Static):
    DEFAULT_CSS = """
    ToolLine {
        height: auto;
        color: $text-warning;
        margin: 0 0 1 1;
    }
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"●  {name}", markup=False)


class ErrorLine(Static):
    DEFAULT_CSS = """
    ErrorLine {
        height: auto;
        color: $text-error;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, text: str) -> None:
        super().__init__(f"⚠  {text}", markup=False)


class CancelLine(Static):
    DEFAULT_CSS = """
    CancelLine {
        height: auto;
        color: $text-muted;
        margin: 0 0 1 1;
    }
    """

    def __init__(self) -> None:
        super().__init__("—  已取消", markup=False)


class AgentMarkdown(Markdown, can_focus=False, can_focus_children=False):
    DEFAULT_CSS = """
    AgentMarkdown {
        height: auto;
        margin: 0 0 1 0;
        padding: 0;
        overflow-y: hidden;
    }
    """
