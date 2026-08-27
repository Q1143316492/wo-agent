"""工具定义：面向模型的 schema + 真正的执行实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from llm.types import ContentBlock, ToolSchema

# 执行函数：接收解析后的参数 dict，返回模型可见的内容块
ToolExecute = Callable[[dict], Awaitable[list[ContentBlock]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema，模型靠它知道怎么调用
    execute: ToolExecute

    @property
    def schema(self) -> ToolSchema:
        """面向模型的声明（name/description/parameters）。"""
        return ToolSchema(name=self.name, description=self.description, parameters=self.parameters)
