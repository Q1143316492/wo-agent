"""Session 测试：append 连续性、派生历史、surface 过滤。"""

from llm.types import (
    FinishChunk,
    FinishReason,
    ModelSource,
    TextBlock,
    TextDelta,
    TokenUsage,
    create_model_message,
    create_tool_result_message,
    create_user_message,
)
from session import Session
from session.events import (
    AssistantChunk,
    AssistantMessageEvent,
    StepEnd,
    StepStart,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from session.session import derive_event_message


def _user(text):
    return create_user_message([TextBlock(text=text)])


def test_append_assigns_contiguous_seq():
    s = Session()
    assert s.seq == 0
    e1 = s.append(TurnStart(turn=0))
    e2 = s.append(UserMessageEvent(message=_user("hi")))
    e3 = s.append(TurnEnd(turn=0))
    assert (e1.seq, e2.seq, e3.seq) == (0, 1, 2)
    assert s.seq == 3
    assert all(a.seq < b.seq for a, b in [(e1, e2), (e2, e3)])


def test_derive_messages_projects_surface_in_order():
    s = Session()
    s.append(TurnStart(turn=0))
    s.append(UserMessageEvent(message=_user("你好")))
    s.append(StepStart(turn=0, step=0))
    s.append(AssistantChunk(turn=0, step=0, chunk=TextDelta(index=0, text="你")))
    s.append(
        AssistantMessageEvent(
            turn=0, step=0,
            message=create_model_message([TextBlock(text="你好")], ModelSource(provider="deepseek", model="m")),
            usage=TokenUsage(input=1, output=1),
        )
    )
    s.append(
        ToolCallEvent(turn=0, step=0, call_id="c1", name="f", arguments="{}")
    )
    s.append(
        ToolResultEvent(turn=0, step=0, message=create_tool_result_message("c1", [TextBlock(text="ok")]))
    )
    s.append(StepEnd(turn=0, step=0))
    s.append(TurnEnd(turn=0))

    msgs = s.derive_messages()
    # user、assistant、tool-result —— 边界和分片被过滤掉
    assert [m.role for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0].content[0].text == "你好"
    assert msgs[1].content[0].text == "你好"
    assert msgs[2].content[0].type == "tool-result"


def test_empty_assistant_message_is_skipped():
    s = Session()
    s.append(UserMessageEvent(message=_user("hi")))
    # 空内容只为承载 usage（max-tokens 步）
    s.append(
        AssistantMessageEvent(
            turn=0, step=0,
            message=create_model_message([], ModelSource(provider="deepseek", model="m")),
            usage=TokenUsage(output=100),
        )
    )
    msgs = s.derive_messages()
    assert len(msgs) == 1
    assert msgs[0].role == "user"


def test_derive_event_message_is_pure_per_event():
    s = Session()
    s.append(TurnStart(turn=0))
    s.append(UserMessageEvent(message=_user("hi")))
    assert derive_event_message(s.events[0].event) is None  # 边界
    assert derive_event_message(s.events[1].event) is not None  # user 消息


def test_events_is_a_snapshot_not_a_mutable_alias():
    s = Session()
    s.append(UserMessageEvent(message=_user("hi")))
    snapshot = s.events
    s.append(TurnEnd(turn=0))
    assert len(snapshot) == 1  # 更早的快照不会增长
    assert len(s.events) == 2
