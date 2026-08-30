"""wo-agent — 工具层。

面向模型的工具 schema（给模型看）+ 工具定义（含执行实现）+ 带守卫的执行
管线。agent 循环通过 `ToolExecutor` 缝使用本包。
"""

from .cancel import bind_tool_cancel, reset_tool_cancel, tool_cancel
from .definition import ToolDefinition
from .executor import RegistryToolExecutor, ToolExecutor, ToolGuard, ToolResult

__all__ = [
    "RegistryToolExecutor",
    "ToolDefinition",
    "ToolExecutor",
    "ToolGuard",
    "ToolResult",
    "tool_cancel",
]
