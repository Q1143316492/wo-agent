"""JsonlSessionStore 测试：往返、缺失、删除、崩溃恢复。"""

import json

import pytest

from llm.types import (
    ModelSource,
    TextBlock,
    TokenUsage,
    create_model_message,
    create_tool_result_message,
    create_user_message,
)
from session import (
    JsonlSessionStore,
    Session,
    SessionFormatUnsupportedError,
    TurnStart,
)
from session.events import (
    AssistantMessageEvent,
    StepStart,
    ToolResultEvent,
    TurnEnd,
    UserMessageEvent,
)


def _build_session() -> Session:
    s = Session()
    s.append(TurnStart(turn=0))
    s.append(UserMessageEvent(message=create_user_message([TextBlock(text="hi")])))
    s.append(StepStart(turn=0, step=0))
    s.append(
        AssistantMessageEvent(
            turn=0, step=0,
            message=create_model_message([TextBlock(text="hello")], ModelSource(provider="deepseek", model="m")),
            usage=TokenUsage(input=1, output=1),
        )
    )
    s.append(
        ToolResultEvent(
            turn=0, step=0,
            message=create_tool_result_message("c1", [TextBlock(text="ok")]),
        )
    )
    s.append(TurnEnd(turn=0))
    return s


def test_save_load_roundtrip_preserves_everything(tmp_path):
    store = JsonlSessionStore(tmp_path)
    original = _build_session()

    store.save(original)
    loaded = store.load(original.id)

    assert loaded is not None
    assert loaded.id == original.id
    assert loaded.seq == original.seq
    # 事件一致，含 seq 和 time
    assert loaded.events == original.events
    # 派生历史一致
    assert loaded.derive_messages() == original.derive_messages()


def test_load_missing_returns_none(tmp_path):
    store = JsonlSessionStore(tmp_path)
    assert store.load("nonexistent") is None


def test_delete_removes_artifact(tmp_path):
    store = JsonlSessionStore(tmp_path)
    s = _build_session()
    store.save(s)
    assert s.id in store.list()
    store.delete(s.id)
    assert s.id not in store.list()
    assert store.load(s.id) is None


def test_list_lists_only_stored(tmp_path):
    store = JsonlSessionStore(tmp_path)
    a, b = _build_session(), _build_session()
    store.save(a)
    assert store.list() == [a.id]


def test_interrupted_turn_recovery(tmp_path):
    store = JsonlSessionStore(tmp_path)
    s = Session()
    s.append(TurnStart(turn=0))
    s.append(UserMessageEvent(message=create_user_message([TextBlock(text="crash")])))
    # 没有 TurnEnd —— 模拟崩溃在半途
    store.save(s)

    loaded = store.load(s.id)
    assert loaded is not None
    # 追加了一条合成的 interrupted TurnEnd
    last = loaded.events[-1].event
    assert last.type == "turn/end"
    assert last.reason == "interrupted"
    # user 消息还在（没有截断）
    assert any(e.event.type == "user/message" for e in loaded.events)


def test_foreign_format_version_refused(tmp_path):
    store = JsonlSessionStore(tmp_path)
    s = _build_session()
    store.save(s)
    path = tmp_path / f"{s.id}.jsonl"
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    header = json.loads(lines[0])
    header["version"] = 999
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        f.writelines(lines[1:])

    with pytest.raises(SessionFormatUnsupportedError):
        store.load(s.id)


def test_save_load_preserves_title(tmp_path):
    store = JsonlSessionStore(tmp_path)
    s = Session()
    s.title = "登录页"
    store.save(s)
    loaded = store.load(s.id)
    assert loaded is not None
    assert loaded.title == "登录页"


def test_list_newest_first(tmp_path):
    store = JsonlSessionStore(tmp_path)
    a, b = Session(), Session()
    store.save(a)
    store.save(b)
    path_b = tmp_path / f"{b.id}.jsonl"
    path_b.touch()
    assert store.list()[0] == b.id
