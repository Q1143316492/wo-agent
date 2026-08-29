# wo-agent

纯 Python 的 agent 学习作品。提供可 import 的 harness：会话、工具循环、可选能力组装。运行时只需 CPython 与本包。

其他项目可以引用本库；本库不依赖、也不绑定任何宿主工程。

可 import 的代码在 `src/`（例如 `from llm import …`）。仓库根是 `pyproject.toml`、`cli/` 与 `examples/`。

## 模块

| 包 | 职责 |
|---|---|
| `src/llm/` | LLM 接入：协议、类型、Provider 适配 |
| `src/session/` | 事件溯源会话与持久化 |
| `src/agent/` | Agent 接口与 ReAct 循环 |
| `src/tools/` | 工具定义与带守卫的执行 |
| `src/skill/` | skill 注册与加载 |
| `src/system_prompt/` | 系统提示分段组装 |
| `src/compose/` | 按 Capability 组装一次运行 |
| `src/compaction/` | 上下文压缩 |
| `src/workspace/` | 工作区内的读/写/编辑与本机命令 |

循环不选择能力；选装发生在组装层。上层只依赖下层协议，不依赖具体 Provider 实现。

## 开发

```sh
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

## CLI

Textual 对话循环。内核仍是 `assemble` + `followup`。`cli/boot.py` 选 Capability，`cli/commands/` 是斜杠命令（不进模型），`cli/tui/` 只画终端。

```sh
.venv/Scripts/pip install -e ".[cli]"
.venv/Scripts/python -m cli
```

需要 `UTAGENT_API_KEY` 或 `DEEPSEEK_API_KEY`。工作区默认进程 cwd（`WO_AGENT_WORKSPACE` 覆盖），会话落在 `.wo-sessions/`。`/help` `/clear` `/quit`。输入 `/` 会弹出补全（Tab 写入，Enter 执行当前项）。

## 示例

- `examples/demo_deepseek.py` — LLM 适配器
- `examples/demo_session.py` — 会话事件与 JSONL
- `examples/demo_agent.py` — 终端 REPL（不用 Textual 的探针）
