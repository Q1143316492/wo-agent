"""Textual 对话画布。循环在 worker 里 ``followup``；斜杠命令走 ``cli.commands``。"""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, Label, Static

from cli.boot import Booted, boot
from cli.chunks import to_ui_event
from cli.commands import CommandOutcome, apply_suggestion, dispatch, parse_line, suggest
from cli.tui.banner import Banner
from cli.tui.suggest import SlashMenu
from cli.tui.widgets import (
    AgentMarkdown,
    CancelLine,
    ErrorLine,
    MetaLine,
    NoteLine,
    StatusBar,
    ThinkLine,
    Thread,
    ToolLine,
    UserLine,
)
from llm.types import StreamChunk

_SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


async def _close_lingering_subprocesses() -> None:
    """Windows Proactor 上 bash 的 transport 必须在 loop.close 之前 close。"""
    loop = asyncio.get_running_loop()
    lingering = getattr(loop, "_transports", None)
    if lingering:
        from asyncio.base_subprocess import BaseSubprocessTransport

        for item in list(lingering.values()):
            if isinstance(item, BaseSubprocessTransport):
                try:
                    item.close()
                except Exception:
                    pass
    await asyncio.sleep(0)


class WoCli(App[None]):
    TITLE = "wo-agent"
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("escape", "slash_or_cancel", "取消", show=False, priority=True),
        Binding("down", "slash_down", show=False, priority=True),
        Binding("up", "slash_up", show=False, priority=True),
        Binding("tab", "slash_complete", show=False, priority=True),
        Binding("ctrl+q", "quit", "退出", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._booted: Booted | None = None
        self._busy = False
        self._spin = 0
        self._last_tool = ""
        self._think_buf = ""
        self._text_buf = ""
        self._think_widget: ThinkLine | None = None
        self._md_widget: AgentMarkdown | None = None
        self._think_dirty = False
        self._text_dirty = False

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status")
        yield Thread(id="thread")
        yield SlashMenu()
        with Horizontal(id="dock"):
            yield Label("❯", id="prompt")
            # 占位符必须以半角开头：空框时光标画在第 0 个字上，中文会占两格。
            yield Input(placeholder=" 问点什么", id="composer", compact=True)
        yield Static("tab 补全    esc 取消    ctrl+q 退出", id="hint")

    def on_mount(self) -> None:
        self._booted = boot(self._on_chunk)
        self._mount_startup()
        self._refresh_status()
        self.set_interval(0.05, self._tick)
        self._focus_composer()

    def _mount_startup(self) -> None:
        self._thread.mount(Banner())
        self._thread.mount(self._meta_line())

    def _meta_line(self) -> MetaLine:
        assert self._booted is not None
        b = self._booted
        return MetaLine(f"{b.session.id[:8]}  ·  {b.workspace}")

    @property
    def _thread(self) -> Thread:
        return self.query_one("#thread", Thread)

    @property
    def _slash(self) -> SlashMenu:
        return self.query_one("#slash", SlashMenu)

    def _focus_composer(self) -> None:
        self.query_one("#composer", Input).focus()

    def _sync_slash(self, typed: str) -> None:
        self._slash.set_suggestions(suggest(typed))

    def _fill_slash(self, name: str) -> None:
        composer = self.query_one("#composer", Input)
        composer.value = apply_suggestion(name)
        composer.cursor_position = len(composer.value)
        self._sync_slash(composer.value)
        self._focus_composer()

    @on(Input.Changed, "#composer")
    def _composer_changed(self, event: Input.Changed) -> None:
        self._sync_slash(event.value)

    def action_slash_down(self) -> None:
        if self._slash.display:
            self._slash.action_cursor_down()

    def action_slash_up(self) -> None:
        if self._slash.display:
            self._slash.action_cursor_up()

    def action_slash_complete(self) -> None:
        name = self._slash.selected_name()
        if name:
            self._fill_slash(name)

    def action_slash_or_cancel(self) -> None:
        if self._slash.display:
            self._slash.set_suggestions(())
            self._focus_composer()
            return
        self.action_cancel_run()

    @on(SlashMenu.OptionSelected)
    def _slash_clicked(self, event: SlashMenu.OptionSelected) -> None:
        event.stop()
        if event.option.id:
            self._fill_slash(event.option.id)

    def _refresh_status(self) -> None:
        b = self._booted
        if b is None:
            return
        if self._busy:
            state = f"{_SPIN[self._spin]}  running"
        else:
            state = "idle"
        self.query_one("#status", StatusBar).update(f"{b.workspace.name}    {state}")

    def _tick(self) -> None:
        self._paint_live()
        if self._busy:
            self._spin = (self._spin + 1) % len(_SPIN)
            self._refresh_status()

    def _scroll_tail(self) -> None:
        self._thread.scroll_end(animate=False)

    def _on_chunk(self, chunk: StreamChunk) -> None:
        self._apply_chunk(chunk)

    def _apply_chunk(self, chunk: StreamChunk) -> None:
        event = to_ui_event(chunk)
        if event is None:
            return
        if event.kind == "think":
            self._think_buf += event.text
            if self._think_widget is None:
                self._think_widget = ThinkLine()
                self._thread.mount(self._think_widget)
            self._think_dirty = True
            return
        if event.kind == "text":
            self._text_buf += event.text
            if self._md_widget is None:
                self._md_widget = AgentMarkdown("")
                self._thread.mount(self._md_widget)
            self._text_dirty = True
            return
        self._commit_live()
        if event.kind == "tool":
            if event.text == self._last_tool:
                return
            self._last_tool = event.text
            self._thread.mount(ToolLine(event.text))
            self._scroll_tail()
        elif event.kind == "error":
            self._thread.mount(ErrorLine(event.text))
            self._scroll_tail()

    def _paint_live(self) -> None:
        if self._think_widget is not None and self._think_dirty:
            self._think_widget.set_text(self._think_buf)
            self._think_dirty = False
        if self._md_widget is not None and self._text_dirty:
            self._md_widget.update(self._text_buf)
            self._text_dirty = False
            self._scroll_tail()

    def _reset_live(self) -> None:
        self._think_buf = ""
        self._text_buf = ""
        self._think_widget = None
        self._md_widget = None
        self._think_dirty = False
        self._text_dirty = False

    def _commit_live(self) -> None:
        self._paint_live()
        self._reset_live()

    def _clear_screen(self) -> None:
        self._reset_live()
        self._thread.remove_children()
        if self._booted is not None:
            self._mount_startup()
        self._scroll_tail()

    def _apply_outcome(self, outcome: CommandOutcome) -> None:
        if outcome.kind == "quit":
            self._request_quit()
            return
        if outcome.kind == "clear":
            self._clear_screen()
            return
        self._thread.mount(NoteLine(outcome.text))
        self._scroll_tail()

    @on(Input.Submitted, "#composer")
    def _submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            self.call_after_refresh(self._focus_composer)
            return
        picked = self._slash.selected_name()
        if picked is not None:
            text = f"/{picked}"
            event.input.value = ""
            self._slash.set_suggestions(())
            parsed = parse_line(text)
            if parsed is not None:
                self._apply_outcome(dispatch(parsed))
            self.call_after_refresh(self._focus_composer)
            return
        parsed = parse_line(text)
        if parsed is not None:
            event.input.value = ""
            self._apply_outcome(dispatch(parsed))
            self.call_after_refresh(self._focus_composer)
            return
        if self._busy or self._booted is None:
            self.call_after_refresh(self._focus_composer)
            return
        event.input.value = ""
        self._thread.mount(UserLine(text))
        self._scroll_tail()
        self._busy = True
        self._last_tool = ""
        self._refresh_status()
        self.call_after_refresh(self._focus_composer)
        self._run_turn(text)

    @work(exclusive=True, group="turn", exit_on_error=False)
    async def _run_turn(self, text: str) -> None:
        assert self._booted is not None
        try:
            await self._booted.agent.followup(text)
            self._booted.store.save(self._booted.session)
        except Exception as exc:
            self._commit_live()
            self._thread.mount(ErrorLine(str(exc)))
        finally:
            self._commit_live()
            self._busy = False
            self._refresh_status()
            self._scroll_tail()
            self.call_after_refresh(self._focus_composer)
            self.set_timer(0.05, self._focus_composer)

    def action_cancel_run(self) -> None:
        if self._booted is None or not self._busy:
            self._focus_composer()
            return
        self._booted.agent.cancel("user")
        self._thread.mount(CancelLine())
        self._scroll_tail()
        self.call_after_refresh(self._focus_composer)

    def action_quit(self) -> None:
        self._request_quit()

    def _request_quit(self) -> None:
        self._quit_after_settle()

    @work(group="quit", exclusive=True, exit_on_error=False)
    async def _quit_after_settle(self) -> None:
        if self._booted is not None:
            self._booted.agent.cancel("quit")
            await self._booted.agent.when_idle()
        await _close_lingering_subprocesses()
        self.exit()
