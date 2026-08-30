# compose

对应 `src/compose/`。选这一次运行要开哪些能力：`compose()` 按名单调用每个 `Capability.mount(ctx)`。`ComposeContext` 上有 `tools`、`skills`、`system_prompt`（还有 `compaction`）。宿主可以把命令表经 `compose(..., commands=table)` 塞进 `ctx.commands`；本包不认识斜杠命令的类型。没列入名单的，对应字段就是空的。

每个 Capability 自己决定往 `ctx` 的哪些字段写。下面三个是**并列的三条**，不是谁包含谁：

```python
from compose import ComposeContext, compose
from llm.types import TextBlock
from skill import SkillCapability
from system_prompt import SystemPromptCapability
from tools import ToolDefinition

class EchoCapability:
    def mount(self, ctx: ComposeContext) -> None:
        async def echo(args: dict):
            return [TextBlock(text=args["text"])]

        ctx.tools.register(ToolDefinition(
            name="echo",
            description="原样返回文本",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            execute=echo,  # 只在本地跑，不发给模型
        ))

ctx = compose(
    SystemPromptCapability(),
    SkillCapability("examples/skills"),
    EchoCapability(),
)
# 发给模型的是 schemas()：name / description / parameters
ctx.tools.schemas()
```

本包只提供 `compose()`。session 和循环由宿主构造。

## 文件

- `compose.py` — `ComposeContext` 一开始 `tools` / `skills` / `system_prompt` 为空。`commands` 由宿主传入。`Capability` 只要有 `mount(ctx)`。`compose()` 按参数顺序调用 `mount`。
