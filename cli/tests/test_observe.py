import json

from cli.observe import (
    argument_preview,
    clip_preview,
    collapse_body,
    format_tool_card,
    header_line,
    result_text,
    wrap_tools,
)
from llm.types import TextBlock, ToolSchema
from tools import ToolResult


class _FakeInner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def schemas(self):
        return [ToolSchema(name="echo", description="e", parameters={"type": "object"})]

    async def execute(self, name: str, arguments: str, cancel=None) -> ToolResult:
        self.calls.append((name, arguments))
        return ToolResult(content=[TextBlock(text="ok")], is_error=False)


async def test_observing_executor_notifies_start_and_end():
    from cli.observe import ObservingToolExecutor

    inner = _FakeInner()
    starts: list[tuple[str, str]] = []
    ends: list[tuple[str, str, bool]] = []
    wrapped = ObservingToolExecutor(
        inner,
        on_start=lambda n, a: starts.append((n, a)),
        on_end=lambda n, t, e: ends.append((n, t, e)),
    )
    result = await wrapped.execute("echo", '{"text":"hi"}')
    assert inner.calls == [("echo", '{"text":"hi"}')]
    assert starts == [("echo", '{"text":"hi"}')]
    assert ends == [("echo", "ok", False)]
    assert result.is_error is False
    assert wrapped.schemas()[0].name == "echo"



def test_bash_preview_is_command():
    assert argument_preview("bash", json.dumps({"command": "curl -L x"})) == "curl -L x"


def test_grep_preview_joins_pattern_and_path():
    assert argument_preview("grep", json.dumps({"pattern": "foo", "path": "src"})) == "foo src"


def test_read_preview_is_file_path():
    assert argument_preview("read", json.dumps({"file_path": "a.py"})) == "a.py"


def test_clip_preview_ellipsis():
    assert clip_preview("abcd", 4) == "abcd"
    assert clip_preview("abcde", 4).endswith("…")
    assert len(clip_preview("abcde", 4)) == 4


def test_collapse_body_keeps_last_eight():
    text = "\n".join(str(i) for i in range(12))
    body = collapse_body(text)
    assert body.startswith("4")
    assert body.endswith("11")
    assert len(body.splitlines()) == 8


def test_header_line_includes_name_and_preview():
    assert header_line("bash", json.dumps({"command": "curl -L x"})) == "bash  curl -L x"


def test_result_text_joins_blocks():
    result = ToolResult(content=[TextBlock(text="a"), TextBlock(text="b")])
    assert result_text(result) == "ab"


def test_wrap_tools_noop_without_both_callbacks():
    inner = _FakeInner()
    assert wrap_tools(inner, None, None) is inner
    assert wrap_tools(inner, lambda *_: None, None) is inner


def test_format_tool_card_collapsed_uses_tail():
    args = json.dumps({"command": "echo hi"})
    body = "\n".join(str(i) for i in range(12))
    card = format_tool_card("bash", args, body, expanded=False)
    lines = card.splitlines()
    assert lines[0] == "●  bash  echo hi"
    assert lines[1] == "4"
    assert lines[-1] == "11"
    full = format_tool_card("bash", args, body, expanded=True)
    assert full.splitlines()[1] == "0"
