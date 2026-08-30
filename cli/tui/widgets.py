"""对话里的消息块。只负责长什么样，不碰循环、不碰命令表。"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static

from cli.observe import format_tool_card


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


class ToolBlock(Static):
    """一次工具调用：命令在标题，输出默认可折。"""

    DEFAULT_CSS = """
    ToolBlock {
        height: auto;
        color: $text-warning;
        margin: 0 0 1 1;
    }
    """

    def __init__(self) -> None:
        super().__init__("", markup=False)
        self._name = ""
        self._arguments = ""
        self._result: str | None = None
        self.expanded = False

    def set_call(self, name: str, arguments: str) -> None:
        self._name = name
        self._arguments = arguments
        self._paint()

    def set_result(self, text: str, is_error: bool = False) -> None:
        self._result = text
        self._paint()

    def toggle(self) -> None:
        self.expanded = not self.expanded
        self._paint()

    def _paint(self) -> None:
        self.update(
            format_tool_card(self._name, self._arguments, self._result, expanded=self.expanded)
        )


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


class QueueStrip(Static):
    """输入框上方的待发队列。不进对话区，claim 之后才变成 UserLine。"""

    DEFAULT_CSS = """
    QueueStrip {
        height: auto;
        color: $text-muted;
        padding: 0 2;
        background: $background;
    }
    """

    def __init__(self) -> None:
        super().__init__("", markup=False, id="queue")
        self.display = False

    def set_items(self, items: tuple[str, ...]) -> None:
        if not items:
            self.update("")
            self.display = False
            return
        self.display = True
        self.update("\n".join(f"queued  {text}" for text in items))


class AgentMarkdown(Markdown, can_focus=False, can_focus_children=False):
    DEFAULT_CSS = """
    AgentMarkdown {
        height: auto;
        margin: 0 0 1 0;
        padding: 0;
        overflow-y: hidden;
    }
    """
