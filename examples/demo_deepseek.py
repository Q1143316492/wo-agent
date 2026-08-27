"""对 DeepSeek 适配器的临时真实请求冒烟测试。

从环境变量读 UTAGENT_API_KEY（UTAgent 的 key），向 deepseek-v4-flash 发一次
请求，打印组装好的回答。绝不打印 key。
"""

import asyncio
import os

from llm.assembler import BlockAssembler
from llm.deepseek import DeepSeekConfig, DeepSeekProvider
from llm.protocol import LLMRequest
from llm.types import (
    FinishChunk,
    ReasoningDelta,
    TextBlock,
    TextDelta,
    create_user_message,
)


async def main() -> None:
    key = os.environ.get("UTAGENT_API_KEY", "")
    if not key:
        print("UTAGENT_API_KEY is not set")
        return

    provider = DeepSeekProvider(
        DeepSeekConfig(api_key=key, base_url="https://api.deepseek.com", model="deepseek-v4-flash")
    )
    request = LLMRequest(
        provider="deepseek",
        model="deepseek-v4-flash",
        messages=[create_user_message([TextBlock(text="用一句话回答：1+1 等于几？")])],
        max_tokens=200,
    )

    assembler = BlockAssembler()
    print("--- stream ---", flush=True)
    async for chunk in provider.stream(request):
        assembler.push(chunk)
        if isinstance(chunk, TextDelta):
            print(chunk.text, end="", flush=True)
        elif isinstance(chunk, ReasoningDelta):
            print(f"\n[think] {chunk.text}", flush=True)
        elif isinstance(chunk, FinishChunk):
            reason = chunk.reason
            if reason.kind == "error":
                print(f"\n[error] {reason.failure.code}: {reason.failure.message}", flush=True)
            else:
                print(f"\n[finish] {reason.kind}", flush=True)
    if assembler.usage is not None:
        u = assembler.usage
        print(f"[usage] in={u.input} out={u.output} cache_read={u.cache_read}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
