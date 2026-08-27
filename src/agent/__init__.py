"""wo-agent — agent 循环。

agent 驱动一个 session 走 ReAct 轮次：从会话日志派生历史、流式调 LLM、
组装、经 `ToolExecutor` 缝派发工具。分层铁律：本包只依赖 `llm`、`session`
和 `tools`。挂哪些能力由 `compose()` 在循环之外决定。本包还包含 inbox、循环内重试与压缩触发。
"""

from .agent import Agent, AgentOptions, AgentStatus
from .inbox import Inbox
from .loop import ReactLoopAgent

__all__ = ["Agent", "AgentOptions", "AgentStatus", "Inbox", "ReactLoopAgent"]
