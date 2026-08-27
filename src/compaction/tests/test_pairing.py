"""工具配对切分：不能拆开 assistant tool-call 与对应 tool-result。"""

from llm.types import ModelSource, TextBlock, ToolCallBlock, create_model_message, create_tool_result_message, create_user_message
from session import Session
from session.events import AssistantMessageEvent, ToolResultEvent, UserMessageEvent
from compaction.pairing import tool_pairing_balanced_after, tool_pairing_balanced_before


def _user(text):
    return create_user_message([TextBlock(text=text)])


def test_user_nodes_are_always_balanced():
    s = Session()
    a = s.append(UserMessageEvent(message=_user("a")))
    b = s.append(UserMessageEvent(message=_user("b")))
    assert tool_pairing_balanced_before(s, a.seq)
    assert tool_pairing_balanced_after(s, a.seq)
    assert tool_pairing_balanced_before(s, b.seq)
    assert tool_pairing_balanced_after(s, b.seq)


def test_cannot_cut_between_tool_call_and_result():
    s = Session()
    s.append(UserMessageEvent(message=_user("do it")))
    assistant = s.append(
        AssistantMessageEvent(
            turn=0, step=0,
            message=create_model_message(
                [ToolCallBlock(id="c1", name="echo", arguments="{}")],
                ModelSource(provider="p", model="m"),
            ),
        )
    )
    result = s.append(
        ToolResultEvent(turn=0, step=0, message=create_tool_result_message("c1", [TextBlock(text="ok")]))
    )
    # 切在 assistant 之后 = 拆开尚未闭合的调用
    assert not tool_pairing_balanced_after(s, assistant.seq)
    assert not tool_pairing_balanced_before(s, result.seq)
    # 整对之后才平衡
    assert tool_pairing_balanced_after(s, result.seq)
    assert tool_pairing_balanced_before(s, s.events[0].seq)
