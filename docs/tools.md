# tools

对应 `src/tools/`。给大模型定义工具：schema 给模型看，`execute` 是真正跑的。具体的 `read` / `bash` / `skill` 不在这里，由 Capability 往 `ctx.tools` 注册。

```python
from llm.types import TextBlock
from tools import ToolDefinition

async def echo(args: dict):
    return [TextBlock(text=f'echoed: {args["text"]}')]

tool = ToolDefinition(
    name="echo",
    description="原样返回文本",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    execute=echo,
)

ctx.tools.register(tool)
```

挂上之后，循环会把 `schemas()` 塞进请求；模型调用时走 `execute(name, arguments, cancel=当前轮的取消事件)`。`RegistryToolExecutor` 把该事件放进 contextvar，会起进程的 runner 用 `tool_cancel()` 来读。各工具自己的 `execute(args)` 签名不变。执行抛错会变成 `is_error` 结果，不崩循环。
