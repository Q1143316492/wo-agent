# compaction

对应 `src/compaction/`。对话太长时，把较早一段收成摘要。session 日志不删；下次发给模型的历史变成「摘要 + 后面还留着的消息」。摘要自己调 `provider.stream()`，不走 agent 循环。

```python
from compaction import BasicCompaction, CompactionOptions, LlmSummarizer

engine = BasicCompaction(
    LlmSummarizer(provider, provider_name="deepseek", model="deepseek-chat"),
    CompactionOptions(threshold_chars=24000, retain_chars=6000),
)
await engine.compact_if_needed(session, trigger="pressure")
```

字符数超过 `threshold_chars` 才压；尾部大约 `retain_chars` 原样保留。没有可切的一段就什么也不做。

现在按字符数。`24000` / `6000` 是初值，不是从 dsh 抄的，仓库里没有换算依据。以后：有 token 计量和模型窗口之后，按 dsh 默认做——阈值 = 窗口 × 0.8，尾部 = 窗口 × 0.16（token）。

## 文件

- `protocol.py` — `Summarizer`：一段消息进，摘要字符串出。`CompactionEngine`：`compact_if_needed` / `compact_now`。
- `engine.py` — `BasicCompaction`、`CompactionOptions`。按字符数判断要不要压，切哪一段。
- `pairing.py` — 切分不能拆开一对 tool-call / tool-result。
- `summarizer.py` — `LlmSummarizer`：用已有的 `LLMProvider` 做一次无工具请求。`frame_summary` 把摘要包成检查点正文。
- `capability.py` — `CompactionCapability`：`mount` 时把引擎放到 `ctx.compaction`。
