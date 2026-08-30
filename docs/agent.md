# agent

对应 `src/agent/`。驱动一个 `Session` 走一轮又一轮：从日志算出对话、流式调模型、按序跑工具。对外是 `followup` / `steer` / `inject` / `enqueue`；日志由循环自己 `append`。

```python
from agent import AgentOptions, ReactLoopAgent
from session import Session

agent = ReactLoopAgent(
    Session(),
    provider,
    AgentOptions(provider="deepseek", model="deepseek-chat"),
    tools,
)
await agent.followup("在场景里创建一个红色方块")
agent.session.events            # 循环写下的 turn/step/消息
agent.session.derive_messages() # 模型看见的对话
```

`provider` 见 [llm.md](llm.md)，`tools` 由 `compose()` 挂上，见 [compose.md](compose.md)。完整可跑见 `examples/demo_agent.py`。

`followup` 把话放进 inbox 的 next-turn 并唤醒循环，等到 idle 才返回。inbox 里的消息还没进日志：循环 `claim` 之后才 `append(UserMessageEvent(...))`。一次 `followup` 写进去的事件见 [session.md](session.md)。

另外几条也进 inbox，去向不同：

- `steer` 进 next-step 并唤醒。当前这一轮的下一步就会 `claim` 到，不必等下一轮。
- `inject` 也进 next-step，但不唤醒。idle 时 session 仍是空的；下次 `followup` 或 `steer` 才一起被 `claim`。
- `enqueue` 进 next-turn，但不唤醒。当前这一轮照常跑完；循环发现还有 next-turn 再开一轮，一次只 `claim` 队头。`queued()` 按从旧到新列出还没 `claim` 的 `(id, 正文)`；`take_back()` 弹出最新一条。

`cancel(cause)` 中止当前 `stream` 并清空 inbox。`cancel(cause, keep_inbox=True)` 只停当前轮，next-turn 留下。`_ensure_running` 看到还有待发，会再开一轮，于是队头接着跑。退出用默认的 `cancel`，队列丢掉。

一轮 turn 里可以有多步 step。模型要调工具，循环写下 `tool/call` 和 `tool/result`，再开下一步继续问。`execute` 带上当前轮的取消事件。写完这次 `tool/result` 若取消已置位，本轮 `aborted`，不再问模型下一步。可重试的 LLM 失败（如限流）在同一步内再请求，不写失败的 `assistant/message`；不可重试的（如鉴权）立刻 `turn/end { reason: "error" }`。

发请求前，若构造时传了 `compaction`，循环先 `compact_if_needed(..., trigger="pressure")`。模型报窗口超限，再压一次（`trigger="overflow"`）后重试该步。压缩怎么改表层见 [compaction.md](compaction.md)。系统提示词每步 `assemble()` 进请求，不写 session，见 [system_prompt.md](system_prompt.md)。

循环不 import skill / 工作区 / bash。构造时只收 `tools`、`system_prompt`、`compaction`（都可以空）；挂哪些能力是 `compose()` 的事，循环只消费挂上之后的字段。

谁在用这个循环：

- `cli/boot.py`、`examples/demo_agent.py` 造出 `Session` + `compose(...)`，再交给 `ReactLoopAgent`。
- `cli/tui/app.py`：空闲时 `followup`，立刻画成对话里的用户行；忙时 `enqueue`，只出现在输入框上方的待发列表，`claim` 之后才变成用户行。Escape 调 `cancel(..., keep_inbox=True)`：流在吐字时停；已经在跑 bash / `rg` 时同一把取消事件把进程杀掉，`followup` 尽快回到 idle。斜杠走 `Booted.commands`（help/clear/quit/resume/new/name）。状态栏加总 `AssistantMessageEvent.usage`；忙时区分 `thinking` 与 `running <工具>`。工具块来自 `boot` 包装的 `execute`（命令 + 可折输出，`Ctrl+O` 展开），不来自流里的工具名分片。一轮结束后 `store.save(session)`。退出走 `cancel("quit")`，队列丢掉。

## 文件

- `agent.py` — `Agent` 契约：`followup` / `steer` / `inject` / `enqueue` / `queued` / `take_back` / `cancel`。`AgentOptions` 是请求用的模型旋钮。
- `inbox.py` — 两级队列：next-turn 与 next-step。`claim` 先倒空 next-step，轮次开头再取一条 next-turn。`peek_turns` / `pop_last_turn` 给终端列队和收回。
- `loop.py` — `ReactLoopAgent`：实现上面的契约，写 session、调 `provider.stream`、经 `tools.execute` 跑工具。
