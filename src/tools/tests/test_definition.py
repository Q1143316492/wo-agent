"""ToolDefinition 的面向模型 schema 测试。"""

from llm.types import ToolSchema
from tools import ToolDefinition


def test_schema_is_model_facing():
    async def execute(args):
        return []

    tool = ToolDefinition(
        name="echo", description="返回文本",
        parameters={"type": "object"}, execute=execute,
    )
    assert isinstance(tool.schema, ToolSchema)
    assert tool.schema.name == "echo"
    assert tool.schema.description == "返回文本"
    assert tool.schema.parameters == {"type": "object"}
