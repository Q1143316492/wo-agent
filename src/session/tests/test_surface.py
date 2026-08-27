"""表层折叠：replace 改投影，日志不删。"""

from llm.types import ModelSource, TextBlock, create_model_message, create_user_message
from session import Session, SurfaceReplace, UserMessageEvent
from session.events import AssistantMessageEvent, TurnStart


def _user(text):
    return create_user_message([TextBlock(text=text)])


def test_replace_hides_shadowed_messages_log_keeps_them():
    s = Session()
    s.append(TurnStart(turn=0))
    first = s.append(UserMessageEvent(message=_user("old-1")))
    second = s.append(UserMessageEvent(message=_user("old-2")))
    s.append(
        AssistantMessageEvent(
            turn=0, step=0,
            message=create_model_message([TextBlock(text="ack")], ModelSource(provider="p", model="m")),
        )
    )
    assert [m.content[0].text for m in s.derive_messages()] == ["old-1", "old-2", "ack"]

    checkpoint = create_user_message([TextBlock(text="SUMMARY")])
    replace = s.append(
        UserMessageEvent(
            message=checkpoint,
            surface_op=SurfaceReplace(start=first.seq, end=second.seq),
            source_event_seqs=(first.seq, second.seq),
        )
    )
    texts = [m.content[0].text for m in s.derive_messages()]
    assert texts == ["SUMMARY", "ack"]
    assert s.surface_seqs() == [replace.seq, s.events[3].seq]
    # 日志仍有被遮蔽的两条
    assert any(e.event.type == "user/message" and e.seq == first.seq for e in s.events)
    assert len(s.events) == 5


def test_append_after_replace_stays_visible():
    s = Session()
    a = s.append(UserMessageEvent(message=_user("a")))
    b = s.append(UserMessageEvent(message=_user("b")))
    s.append(
        UserMessageEvent(
            message=_user("SUM"),
            surface_op=SurfaceReplace(start=a.seq, end=b.seq),
            source_event_seqs=(a.seq, b.seq),
        )
    )
    s.append(UserMessageEvent(message=_user("new")))
    assert [m.content[0].text for m in s.derive_messages()] == ["SUM", "new"]


def test_nested_replace_uses_current_surface_seqs():
    s = Session()
    a = s.append(UserMessageEvent(message=_user("a")))
    b = s.append(UserMessageEvent(message=_user("b")))
    c = s.append(UserMessageEvent(message=_user("c")))
    first = s.append(
        UserMessageEvent(
            message=_user("S1"),
            surface_op=SurfaceReplace(start=a.seq, end=b.seq),
            source_event_seqs=(a.seq, b.seq),
        )
    )
    # 表层现在是 S1, c。再压整段。
    second = s.append(
        UserMessageEvent(
            message=_user("S2"),
            surface_op=SurfaceReplace(start=first.seq, end=c.seq),
            source_event_seqs=(first.seq, c.seq),
        )
    )
    assert [m.content[0].text for m in s.derive_messages()] == ["S2"]
    assert s.surface_seqs() == [second.seq]


def test_legacy_user_message_without_surface_op_appends():
    from session.serialize import dict_to_event, event_to_dict

    event = UserMessageEvent(message=_user("hi"))
    payload = event_to_dict(event)
    del payload["surface_op"]
    del payload["source_event_seqs"]
    restored = dict_to_event(payload)
    assert restored.surface_op == "append"
    assert restored.source_event_seqs == ()
