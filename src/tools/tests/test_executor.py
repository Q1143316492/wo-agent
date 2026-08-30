"""RegistryToolExecutor 测试：注册、执行、守卫、错误处理。"""

from llm.types import TextBlock
from tools import RegistryToolExecutor, ToolDefinition


def _echo() -> ToolDefinition:
    async def execute(args):
        return [TextBlock(text=f'echoed: {args["text"]}')]

    return ToolDefinition(
        name="echo", description="原样返回文本",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        execute=execute,
    )


async def test_register_and_execute():
    executor = RegistryToolExecutor()
    executor.register(_echo())
    result = await executor.execute("echo", '{"text":"hi"}')
    assert result.is_error is False
    assert result.content[0].text == "echoed: hi"


async def test_schemas_returns_model_facing_declaration():
    executor = RegistryToolExecutor()
    executor.register(_echo())
    schemas = executor.schemas()
    assert len(schemas) == 1
    assert schemas[0].name == "echo"
    assert schemas[0].parameters["properties"]["text"]["type"] == "string"


async def test_unknown_tool_is_error():
    executor = RegistryToolExecutor()
    result = await executor.execute("nope", "{}")
    assert result.is_error is True


async def test_guard_denies_monotonically():
    class DenyEcho:
        async def check(self, name, arguments):
            return "echo 被禁用" if name == "echo" else None

    executor = RegistryToolExecutor()
    executor.register(_echo())
    executor.add_guard(DenyEcho())
    result = await executor.execute("echo", '{"text":"hi"}')
    assert result.is_error is True
    assert "denied" in result.content[0].text


async def test_execute_error_becomes_is_error_result():
    async def boom(args):
        raise RuntimeError("工具内部炸了")

    executor = RegistryToolExecutor()
    executor.register(ToolDefinition(name="boom", description="", parameters={}, execute=boom))
    result = await executor.execute("boom", "{}")
    assert result.is_error is True
    assert "工具内部炸了" in result.content[0].text


async def test_empty_arguments_parses_to_empty_dict():
    async def execute(args):
        return [TextBlock(text=f"keys={sorted(args)}")]

    executor = RegistryToolExecutor()
    executor.register(ToolDefinition(name="t", description="", parameters={}, execute=execute))
    result = await executor.execute("t", "")
    assert result.content[0].text == "keys=[]"


async def test_execute_binds_cancel_event():
    import asyncio

    from tools.cancel import tool_cancel

    seen: list[bool] = []

    async def execute(args):
        ev = tool_cancel()
        seen.append(ev is not None and ev.is_set() is False)
        return [TextBlock(text="ok")]

    executor = RegistryToolExecutor()
    executor.register(ToolDefinition(name="t", description="", parameters={}, execute=execute))
    cancel = asyncio.Event()
    await executor.execute("t", "{}", cancel=cancel)
    assert seen == [True]
    assert tool_cancel() is None
