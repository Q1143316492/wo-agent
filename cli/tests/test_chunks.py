from llm.types import FinishChunk, FinishReason, LlmFailure, TextDelta, ToolCallDelta

from cli.chunks import to_ui_event


def test_text_delta():
    event = to_ui_event(TextDelta(index=0, text="你好"))
    assert event is not None
    assert event.kind == "text"
    assert event.text == "你好"


def test_tool_name_not_a_ui_event():
    assert to_ui_event(ToolCallDelta(index=0, id="1", name="bash")) is None
    assert to_ui_event(ToolCallDelta(index=0, id="1", arguments_delta="{")) is None


def test_error_finish():
    event = to_ui_event(
        FinishChunk(reason=FinishReason(kind="error", failure=LlmFailure(message="nope", code="AUTH")))
    )
    assert event is not None
    assert event.kind == "error"
    assert "AUTH" in event.text
