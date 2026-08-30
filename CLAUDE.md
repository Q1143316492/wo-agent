# wo-agent

纯 Python agent harness 学习作品，对齐 deepseek-harness（dsh）的模块拆分。运行时只要求 CPython + 本包（现依赖仅 `httpx`）；宿主（Unity / UE / 桌宠 / 服务器进程）`import` 后即可用。本仓独立存在，不依赖、也不绑定任何宿主工程。

> 这是 Claude Code 的项目上下文文件——在本仓写代码前自动读取。只放「不读代码看不出的约束」。

## 包布局

可 import 的包在 `src/`（如 `from llm import …`）；仓库根是 `pyproject.toml`、`cli/` 与 `examples/`。`cli/` 是产品终端，不进 `src/`，不改循环。斜杠命令在 `cli/commands/`（不进模型）；画布在 `cli/tui/`。

## 架构分层（单向依赖，禁止反向）

```
compose/  →  agent/ → session/ → llm/
         ↘  skill/  → tools/
         ↘  system_prompt/
         ↘  compaction/ → session/, llm/
         ↘  workspace/  → tools/, system_prompt/
```

- 上层只依赖下层的**接口/协议（Protocol）**，不依赖具体实现。
- `llm/deepseek.py` 是唯一知道 DeepSeek 特例的适配器，上层不得 import 它。
- `agent/` 依赖 `llm` 的公共组装器（`BlockAssembler`）与协议（`LLMProvider`），但绝不 import `llm.deepseek`。
- 循环不知道挂了哪些能力。选装发生在 `compose(...)`；循环只消费 `ctx.tools`、`ctx.system_prompt`、`ctx.compaction`。宿主若接入，也是 Capability 往 `ctx.tools` 注册工具，不在 `src/` 里与 `agent/` 并列新核心层。

## 核心设计（对齐 dsh）

- **事件溯源**：`session/` 是 append-only 事件日志，模型可见历史由 `derive_messages()` 派生。"模型可见 = 必须落日志"。这本日志就是审计与复盘的权威；不要为人读另写 `agent_*.log`。`session-stats` / `session-query` / `session-telemetry` 无消费方不做。
- **分片流**：`llm/` 用 shard 流协议（block-start / delta / block-end / usage / finish）+ 唯一 `BlockAssembler`。
- **无特权核心**：agent 循环是实现 `Agent` 接口的插件。`followup` / `steer` / `inject` / `enqueue` 进 inbox；claim 后才落 `user/message`。宿主领域流程不进循环。 `cancel(..., keep_inbox=True)` 停当前轮但留下 next-turn。
- **可重试失败**：`llm.errors.is_retryable`；循环在同一步再请求，不写失败的 assistant/message。
- **组合层**：插件往 `ctx` 注册；`compose()` 按序挂载。session 与循环由宿主构造。不引入 Cordis / profile yaml。
- **系统提示词**：插件往 `ctx.system_prompt` 注册有序段；循环每步 `assemble()` 后作为请求首条 system 消息。不进 session 日志（由注册表重建，对齐 dsh）。
- **能力缝**：skill、工作区（含可选 `bash`）、压缩都是选装。`ToolExecutor` 仍是循环的执行缝。压缩挂 `ctx.compaction`；循环在发请求前 `compact_if_needed`。日志不删，`surfaceOp: replace` 改投影。工作区围栏在 `workspace/` 的路径解析里，管不住 `bash`。

## 定位边界（不做成大而全 agent）

不复刻 Claude Code / Codex + skill 那类「通用编码宿主 + 可扩展知识」产品。价值在两条：

1. **可控规模的 Python 内核**：给 Python / C# 宿主一个能 `import` 的 loop。
2. **极窄宿主**：编辑器里工具少、检查硬——模型没有离开这个世界的路。

判别：下一步若是全量 skill 生态、产品级 subagent、沙箱升权，就是在做小 Claude Code，停。本机 `bash` 工具不是那条路——它是工作区闭环（改文件 → 跑命令 → 看输出）。

## 注释规范

- **默认中文**；技术术语与标识符保留英文（如 `BlockAssembler`、`request/header`、`tool-call`）。
- **不写开发期阶段描述**（如 "M2"、"缺口②"、"下一步"）——那是开发期讨论，脱离上下文不可读。
- docstring 写"是什么 + 为什么"；设计理由可保留，用中文写。

## 测试

- 每个模块自带 `tests/` 目录，pytest 运行。
- 单元测试**不依赖网络、不依赖真实 LLM key**（fake provider / httpx MockTransport）。

## 开发

```sh
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

终端真实对话（需设置 `DEEPSEEK_API_KEY`）：

```sh
.venv/Scripts/pip install -e ".[cli]"
.venv/Scripts/python -m cli
```

不用 Textual 的探针：`PYTHONUTF8=1 .venv/Scripts/python examples/demo_agent.py`
