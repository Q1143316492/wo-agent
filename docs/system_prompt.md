# system_prompt

对应 `src/system_prompt/`。给大模型拼系统提示词：往 `SystemPromptRegistry` 注册有序段，循环每步 `assemble()` 成请求第一条 system 消息。不进 session，由注册表当场重建。

```python
from system_prompt import PromptSection, SystemPromptRegistry

prompt = SystemPromptRegistry()
prompt.section(PromptSection(name="harness:identity", order=-100, text="You are wo-agent."))
prompt.section(PromptSection(name="skill:catalog", order=100, text=lambda: "skill: identity"))

prompt.assemble()
# -> "You are wo-agent.\n\nskill: identity"
```

`text` 可以是字符串或 `() -> str`（assemble 时再求值）。按 `order` 升序、空段丢掉、重名拒绝。

`AgentsMdCapability(root, stop_at=家目录)` 从 `root` 往上找 `AGENTS.md` 和 `CLAUDE.md`，远的先拼、近的后拼。没有文件就不注册。`cli/boot.py` 会挂上它。

## 文件

- `registry.py` — `PromptSection` / `SystemPromptRegistry`
- `capability.py` — 固定身份段
- `agents_md.py` — 往上收集 `AGENTS.md` / `CLAUDE.md`
