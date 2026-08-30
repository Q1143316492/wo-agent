# llm

对应 `src/llm/`。给大模型发一次请求：`LLMRequest` 进去，流出分片；`BlockAssembler` 把分片拼成内容块。`finish` 是唯一终止，错误也走它，不在流上抛异常。

```python
from llm.assembler import BlockAssembler
from llm.deepseek import DeepSeekConfig, DeepSeekProvider
from llm.protocol import LLMRequest
from llm.types import TextBlock, create_user_message

provider = DeepSeekProvider(DeepSeekConfig(api_key=key, model="deepseek-chat"))
request = LLMRequest(
    provider="deepseek",
    model="deepseek-chat",
    messages=[create_user_message([TextBlock(text="1+1 等于几？")])],
)

assembler = BlockAssembler()
async for chunk in provider.stream(request):
    assembler.push(chunk)

assembler.blocks()   # 拼好的内容块
assembler.finish     # stop / tool-calls / error / ...
```

上层只依赖 `protocol` / `types`，不要 import `deepseek`。

## 文件

通用（学这几份就够）：

- `types.py` — 词汇。内容块、消息、流分片、`ToolSchema`。和哪家 API 无关。
- `registry.py` — `ModelRegistry`：按名登记 provider。目前很薄。
- `protocol.py` — `LLMRequest` + `LLMProvider.stream()`。各家适配器都实现这个接口。
- `assembler.py` — `BlockAssembler`：分片拼成内容块。共享实现，适配器不要自己拼。

- `errors.py` — 稳定错误码和 `is_retryable`。循环按 code 决定重不重试。

DeepSeek 专用：

- `deepseek.py` — `DeepSeekProvider` / `DeepSeekConfig`。SSE、usage 换算、不支持图片等特例都在这里。

具体来说

ModelRegistry 注册 name => LLMProvider

`LLMRequest` 是一次调用要发什么（消息、模型、tools）。`request.provider` 只是字符串标签，如 `"deepseek"`。

`LLMProvider` 是接口：只要 `stream(request)` 出分片。循环只认这个。

`DeepSeekProvider` 实现这个接口，把请求翻成 DeepSeek 的 HTTP/SSE，再吐通用分片。

`stream(request, signal=None)`：输入是 `LLMRequest`，可选 `signal` 用来取消。输出是一串 `StreamChunk`，最后一条一定是 `finish`。失败也走分片，不抛异常。

你在终端输入 `1+1等于几？` 时：

1. `followup("1+1等于几？")` 把这句话写成一条 user 消息。
2. 循环拼出 `LLMRequest`：系统提示 + 这条用户消息（以及更早的对话）。**这包 messages 才是发给大模型的。**
3. `stream(request)` 把请求 POST 到 DeepSeek；模型一个字一个字回来。
4. 你屏幕上看到的 `2`、`。` 是每个 `TextDelta` 打出来的（给真人看的增量）。
5. `BlockAssembler` 把分片拼成完整的 `TextBlock("2。")`，存进 session。
6. 你再发下一句时，模型看到的是拼好的 `"2。"`，不是那些 delta。
