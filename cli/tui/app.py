"""Textual 对话画布。idle 时 ``followup``；忙时 ``enqueue`` 进下一轮队列。
斜杠命令走 ``cli.commands``。Escape 取消当前轮并保留队列。
"""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, Label, Static

from cli.boot import Booted, boot
from cli.commands import CommandContext, CommandOutcome, apply_suggestion, parse_line
from cli.commands.dispatch import TABLE
from cli.chunks import to_ui_event
from cli.usage import sum_usage
from cli.tui.banner import Banner
from cli.tui.suggest import SlashMenu
from cli.tui.widgets import (
    AgentMarkdown,
    CancelLine,
    ErrorLine,
    MetaLine,
    NoteLine,
    QueueStrip,
    StatusBar,
        ThinkLine,
        Thread,
        ToolBlock,
        UserLine,
)
from llm.types import StreamChunk
from session import Session

_SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class Composer(Input):
    """输入焦点在框里时，App 级 Escape 到不了；这里转给 App。"""

    BINDINGS = [
        Binding("escape", "escape", "取消", show=False, priority=True),
        Binding("up", "up", "收回队列", show=False, priority=True),
        Binding("ctrl+o", "toggle_tool", show=False, priority=True),
    ]

    def action_escape(self) -> None:
        self.app.action_slash_or_cancel()

    def action_up(self) -> None:
        self.app.action_slash_up()

    def action_toggle_tool(self) -> None:
        self.app.action_toggle_tool()


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
        Binding("ctrl+o", "toggle_tool", "展开工具", show=False, priority=True),
        Binding("ctrl+q", "quit", "退出", show=False),
    ]

    def __init__(self, resume: str | None = None) -> None:
        super().__init__()
        self._resume = resume
        self._booted: Booted | None = None
        self._busy = False
        self._cancel_shown = False
        self._spin = 0
        self._running_tool: str | None = None
        self._think_buf = ""
        self._text_buf = ""
        self._think_widget: ThinkLine | None = None
        self._md_widget: AgentMarkdown | None = None
        self._think_dirty = False
        self._text_dirty = False
        self._queued_items: tuple[tuple[str, str], ...] = ()
        self._promoted: set[str] = set()
        self._taken_back: set[str] = set()
        self._expect_promote_text: str | None = None

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status")
        yield Thread(id="thread")
        yield SlashMenu()
        yield QueueStrip()
        with Horizontal(id="dock"):
            yield Label("❯", id="prompt")
            # 占位符必须以半角开头：空框时光标画在第 0 个字上，中文会占两格。
            yield Composer(placeholder=" 问点什么", id="composer", compact=True)
        yield Static("tab 补全    忙时回车排队    esc 取消当前    ↑ 收回队列    ctrl+o 展开工具    ctrl+q 退出", id="hint")

    def on_mount(self) -> None:
        self._booted = boot(
            self._on_chunk,
            resume=self._resume,
            on_tool_start=self._on_tool_start,
            on_tool_end=self._on_tool_end,
        )
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
        title = f"  ·  {b.session.title}" if b.session.title else ""
        return MetaLine(f"{b.session.id[:8]}{title}  ·  {b.workspace}")

    @property
    def _thread(self) -> Thread:
        return self.query_one("#thread", Thread)

    @property
    def _slash(self) -> SlashMenu:
        return self.query_one("#slash", SlashMenu)

    def _table(self):
        if self._booted is not None and self._booted.commands is not None:
            return self._booted.commands
        return TABLE

    def _command_ctx(self) -> CommandContext:
        b = self._booted
        if b is None:
            return CommandContext()
        return CommandContext(
            store=b.store,
            session=b.session,
            workspace=b.workspace,
            sessions_dir=b.sessions_dir,
        )

    def _focus_composer(self) -> None:
        self.query_one("#composer", Composer).focus()

    def _sync_slash(self, typed: str) -> None:
        self._slash.set_suggestions(self._table().suggest(typed))

    def _fill_slash(self, name: str) -> None:
        composer = self.query_one("#composer", Composer)
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
            return
        self._take_back_queued()

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
            if self._running_tool:
                state = f"{_SPIN[self._spin]}  running {self._running_tool}"
            else:
                state = f"{_SPIN[self._spin]}  thinking"
        else:
            state = "idle"
        u = sum_usage(b.session)
        usage = f"in={u.input} out={u.output}"
        if u.cache_read:
            usage += f" cache={u.cache_read}"
        self.query_one("#status", StatusBar).update(f"{b.workspace.name}    {state}    {usage}")

    def _tick(self) -> None:
        self._paint_live()
        self._sync_queue()
        if self._busy:
            self._spin = (self._spin + 1) % len(_SPIN)
            self._refresh_status()

    def _sync_queue(self) -> None:
        """输入框上方只列还没 claim 的 next-turn；队头被 claim 后再写成 UserLine。"""
        if self._booted is None:
            return
        current = self._booted.agent.queued()
        if self._expect_promote_text is not None:
            want = self._expect_promote_text
            self._expect_promote_text = None
            for qid, text in current:
                if text == want:
                    self._promoted.add(qid)
                    break
        current_ids = {qid for qid, _ in current}
        for qid, text in self._queued_items:
            if qid in current_ids or qid in self._taken_back or qid in self._promoted:
                continue
            self._commit_live()
            self._thread.mount(UserLine(text))
            self._promoted.add(qid)
            self._cancel_shown = False
            self._scroll_tail()
        self._queued_items = current
        visible = tuple(text for qid, text in current if qid not in self._promoted)
        self.query_one("#queue", QueueStrip).set_items(visible)

    def _take_back_queued(self) -> None:
        if self._booted is None:
            return
        composer = self.query_one("#composer", Composer)
        if composer.value.strip() or composer.cursor_position != 0:
            return
        self._sync_queue()
        visible = [(qid, text) for qid, text in self._queued_items if qid not in self._promoted]
        if not visible:
            return
        last_id = visible[-1][0]
        text = self._booted.agent.take_back()
        if text is None:
            return
        self._taken_back.add(last_id)
        composer.value = text
        composer.cursor_position = len(text)
        self._sync_queue()
        self._focus_composer()

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
        if event.kind == "error":
            self._thread.mount(ErrorLine(event.text))
            self._scroll_tail()

    def _on_tool_start(self, name: str, arguments: str) -> None:
        self.call_later(self._apply_tool_start, name, arguments)

    def _on_tool_end(self, name: str, text: str, is_error: bool) -> None:
        self.call_later(self._apply_tool_end, name, text, is_error)

    def _apply_tool_start(self, name: str, arguments: str) -> None:
        self._commit_live()
        self._running_tool = name
        block = ToolBlock()
        block.set_call(name, arguments)
        self._thread.mount(block)
        self._refresh_status()
        self._scroll_tail()

    def _apply_tool_end(self, name: str, text: str, is_error: bool) -> None:
        self._running_tool = None
        blocks = list(self.query(ToolBlock))
        if blocks:
            blocks[-1].set_result(text, is_error)
        self._refresh_status()
        self._scroll_tail()

    def action_toggle_tool(self) -> None:
        blocks = list(self.query(ToolBlock))
        if not blocks:
            return
        blocks[-1].toggle()
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
        if outcome.kind in ("new_session", "load_session"):
            self._switch_session(outcome)
            return
        self._thread.mount(NoteLine(outcome.text))
        self._scroll_tail()

    @work(exclusive=True, group="turn", exit_on_error=False)
    async def _switch_session(self, outcome: CommandOutcome) -> None:
        assert self._booted is not None
        b = self._booted
        b.agent.cancel("quit")
        await b.agent.when_idle()
        if outcome.kind == "new_session":
            session = Session()
        else:
            session = b.store.load(outcome.session_id)
            if session is None:
                self._thread.mount(NoteLine("会话不存在。"))
                self._scroll_tail()
                return
        b.replace_session(session)
        self._busy = False
        self._running_tool = None
        self._queued_items = ()
        self._promoted.clear()
        self._taken_back.clear()
        self._expect_promote_text = None
        self._clear_screen()
        self._refresh_status()
        self.call_after_refresh(self._focus_composer)

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
                self._apply_outcome(self._table().dispatch(parsed, self._command_ctx()))
            self.call_after_refresh(self._focus_composer)
            return
        parsed = parse_line(text)
        if parsed is not None:
            event.input.value = ""
            self._apply_outcome(self._table().dispatch(parsed, self._command_ctx()))
            self.call_after_refresh(self._focus_composer)
            return
        if self._booted is None:
            self.call_after_refresh(self._focus_composer)
            return
        event.input.value = ""
        if self._busy:
            # 不打断当前轮，也不立刻写成 UserLine；claim 之后 _sync_queue 再挂。
            self._booted.agent.enqueue(text)
            self._sync_queue()
            self.call_after_refresh(self._focus_composer)
            return
        self._thread.mount(UserLine(text))
        self._scroll_tail()
        self._expect_promote_text = text
        self._busy = True
        self._cancel_shown = False
        self._running_tool = None
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
            self._running_tool = None
            self._refresh_status()
            self._scroll_tail()
            self.call_after_refresh(self._focus_composer)
            self.set_timer(0.05, self._focus_composer)

    def action_cancel_run(self) -> None:
        if self._booted is None or not self._busy:
            self._focus_composer()
            return
        self._booted.agent.cancel("user", keep_inbox=True)
        self._commit_live()
        if not self._cancel_shown:
            self._cancel_shown = True
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
