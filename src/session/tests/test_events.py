"""SessionEvent 词汇测试：类型判别与 surface 资格。"""

from session.events import (
    AssistantMessageEvent,
    CompactionStart,
    ToolResultEvent,
    TurnStart,
    UserMessageEvent,
    is_surface_event,
)
from llm.types import TextBlock, create_tool_result_message, create_user_message


def test_turn_start_discriminator():
    ev = TurnStart(turn=1)
    assert ev.type == "turn/start"


def test_surface_eligibility():
    user = UserMessageEvent(message=create_user_message([TextBlock(text="hi")]))
    assert is_surface_event(user)

    result = ToolResultEvent(
        turn=0,
        step=0,
        message=create_tool_result_message("c1", [TextBlock(text="ok")]),
    )
    assert is_surface_event(result)

    assistant = AssistantMessageEvent(turn=0, step=0, message=create_user_message([TextBlock(text="x")]))
    assert is_surface_event(assistant)

    assert not is_surface_event(TurnStart(turn=0))
    assert not is_surface_event(CompactionStart(compaction_id="x"))
