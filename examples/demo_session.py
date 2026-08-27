"""可读的 session 使用示例：事件溯源会话 + 持久化。

演示一件事：一次 ReAct 对话（用户消息 → 思考/回复 → 工具调用 → 工具结果）
如何作为事件追加进会话日志，derive_messages 派生"模型将看到的历史"，
再保存成 JSONL、重载还原。

运行：.venv/Scripts/python examples/demo_session.py
"""

import tempfile
from pathlib import Path

from llm.types import (
    ModelSource,
    ReasoningBlock,
    TextBlock,
    TokenUsage,
    create_model_message,
    create_tool_result_message,
    create_user_message,
)
from session import JsonlSessionStore, Session
from session.events import (
    AssistantMessageEvent,
    StepEnd,
    StepStart,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)


def main() -> None:
    # 1. 建一个会话（事件日志）
    session = Session()

    # 2. 追加一次完整对话——每个"事实"都是一条事件
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(
        message=create_user_message([TextBlock(text="在场景里创建一个红色方块")])
    ))
    session.append(StepStart(turn=0, step=0))
    session.append(AssistantMessageEvent(
        turn=0, step=0,
        message=create_model_message(
            [ReasoningBlock(text="用户要创建方块，用 create_cube 工具"),
             TextBlock(text="我来创建一个红色方块")],
            ModelSource(provider="deepseek", model="deepseek-v4-flash"),
        ),
        usage=TokenUsage(input=100, output=20),
    ))
    session.append(ToolCallEvent(turn=0, step=0, call_id="c1", name="create_cube", arguments='{"color":"red"}'))
    session.append(ToolResultEvent(
        turn=0, step=0,
        message=create_tool_result_message("c1", [TextBlock(text='{"ok": true, "name": "Cube"}')]),
    ))
    session.append(StepEnd(turn=0, step=0))
    session.append(TurnEnd(turn=0))

    # 3. 派生"模型将看到的历史"——这就是以后塞进 LLMRequest 的消息
    print("=== 模型将看到的消息（derive_messages）===")
    for msg in session.derive_messages():
        parts = " / ".join(f"{b.type}" for b in msg.content)
        print(f"  [{msg.role}] {parts}: {msg.content[0]!r}")

    # 4. 保存成 JSONL（原子写，一个会话一个文件）
    out_dir = Path(tempfile.mkdtemp(prefix="wo-agent-session-"))
    store = JsonlSessionStore(out_dir)
    store.save(session)
    print(f"\n已保存到 {out_dir / (session.id + '.jsonl')}")

    # 5. 重载还原，验证事件和派生历史一致
    loaded = store.load(session.id)
    assert loaded is not None
    print(f"重载事件数: {loaded.seq}  ==  原事件数: {session.seq}")
    print(f"重载后派生历史一致: {loaded.derive_messages() == session.derive_messages()}")


if __name__ == "__main__":
    main()
