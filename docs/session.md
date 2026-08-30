# session

对应 `src/session/`。一份只追加的事件日志；模型看到的对话是从它算出来的，不另存一份消息数组。给循环、压缩、持久化共用。

```python
from llm.types import TextBlock, create_user_message
from session import Session
from session.events import TurnStart, UserMessageEvent

session = Session()
session.title = "登录页"   # 可选；写入 jsonl 头，不进模型可见历史
session.append(TurnStart(turn=0))
session.append(UserMessageEvent(
    message=create_user_message([TextBlock(text="在场景里创建一个红色方块")]),
))
session.events            # 两条都在
session.derive_messages() # 只有 user 那条
```

完整一轮（含工具、存盘、重载）见 `examples/demo_session.py`。

`events` 里两条都在，`derive_messages()` 只留下 user 那条：能算进对话的只有 `user/message`、`assistant/message`、`tool/result`。空内容的 `assistant/message` 也不进历史，只为记下 usage。

上面是手工 `append`。跑 agent 时，`cli/boot.py` 造出 `Session`（或从 `.jsonl` `load`）交给 `ReactLoopAgent`，由循环往里写。你跟了一句「在场景里创建一个红色方块」时：

1. `followup(...)` 把这句话放进 inbox，还不 `append`。
2. 循环 `claim` 之后才 `append(UserMessageEvent(...))`。
3. 同一步里还会写下 `turn/start`、`step/start`、`request/header`，以及模型吐出的每个 `assistant/chunk`。
4. 步结束时 `append(AssistantMessageEvent(...))`；若有工具，再写 `tool/call` 和 `tool/result`。
5. 下一步循环拼 `LLMRequest` 时调用 `session.derive_messages()`，再把系统提示词插到最前面——系统提示词不进日志，由注册表当场拼，见 [system_prompt.md](system_prompt.md)。
6. 这一包 messages 才是发给模型的。终端上闪过的字来自 chunk；模型下次看到的是拼好的 `assistant/message`。

谁在用这本日志：

- `cli/boot.py` 新建或 `JsonlSessionStore.load`，交给 `ReactLoopAgent`。
- `ReactLoopAgent` 写下几乎所有事件，并用 `derive_messages()` 拼请求。
- `BasicCompaction` 对话太长时写入 `compaction/*`，再用 `replace` 改模型看见的那段。
- `JsonlSessionStore` 把整本日志存成一个 `.jsonl`；重载时未闭合的 turn 补 `turn/end { reason: "interrupted" }`。
- `cli/tui/app.py` 一轮结束后 `store.save(session)`。

压缩不删日志。它先 `append(CompactionStart)`，再写摘要和 `compaction/summary`，然后追加一条带 `surface_op: replace` 的 `user/message`，最后 `CompactionEnd`。`derive_messages()` 走的那串节点各有一个 `seq`（`surface_seqs()`）；`replace` 的 `start` / `end` 是这些 seq，不是 `events` 里的下标。被换掉的事件仍在 `events` 里；下次 `derive_messages()` 看到的是「摘要 + 还留着的消息」。`compaction/*` 自己不算进对话。切分规则见 [compaction.md](compaction.md)。

## 文件

- `events.py` — 日志里每一条事实的类型。循环写 turn/step/消息/分片/工具；压缩写 `compaction/*`。
- `session.py` — `append` 写日志；`derive_messages` / `surface_seqs` / `fold_surface` 算出当前表层。压缩切范围时也走 `fold_surface`。
- `serialize.py` — 同一套类型进出 dict，`.jsonl` 不另造存储格式。
- `persistence.py` — `SessionStore`：save / load / delete / list。
- `jsonl.py` — 一个会话一个 `.jsonl`。实现上面的 `SessionStore`。header 带 `title`；`list()` 按修改时间新→旧。
