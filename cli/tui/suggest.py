"""斜杠补全菜单。候选项来自 ``cli.commands.suggest``，本文件只负责画出列表。"""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from cli.commands import Suggestion


class SlashMenu(OptionList, can_focus=False):
    DEFAULT_CSS = """
    SlashMenu {
        height: auto;
        max-height: 8;
        padding: 0 2;
        background: $background;
        border-top: solid $foreground 12%;
        scrollbar-size-vertical: 1;
        scrollbar-background: $background;
        scrollbar-color: $foreground 22%;
    }
    SlashMenu > .option-list--option-highlighted {
        color: $foreground;
        background: $foreground 12%;
        text-style: none;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="slash", compact=True)
        self.display = False

    def set_suggestions(self, items: Sequence[Suggestion]) -> None:
        if not items:
            self.clear_options()
            self.display = False
            return
        self.set_options(Option(_prompt(item), id=item.name) for item in items)
        self.display = True
        self.highlighted = 0

    def selected_name(self) -> str | None:
        if not self.display:
            return None
        option = self.highlighted_option
        return option.id if option is not None else None


def _prompt(item: Suggestion) -> Text:
    text = Text()
    text.append(f"/{item.name}", style="bold")
    text.append("  ")
    text.append(item.description, style="dim")
    return text
