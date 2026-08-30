# skill

对应 `src/skill/`。给大模型一套可按名加载的任务说明：磁盘上的 markdown 进 `SkillRegistry`，目录给模型看，正文按 kebab-case 名取出。

```python
from skill import FilesystemSkillProvider, SkillRegistry

skills = SkillRegistry()
skills.add_provider(FilesystemSkillProvider("examples/skills"))

skills.list()              # name + description
skills.get("identity")     # 含正文的完整项
skills.catalog_text()      # 模型可见的 <available_skills> 列表
```

文件是 `*.md`（或 `*.md.txt`），名字取 frontmatter 的 `name`，缺省用文件名：

```markdown
---
name: identity
description: 身份说明
---

正文。模型用 `skill` 工具按精确名加载后再照着做。
```

## 文件

- `protocol.py` — 接口。`SkillSummary` 是目录项（名字 + 短描述），`SkillDefinition` 多一份正文。`SkillProvider` 规定来源只要 `list()` / `get()`。
- `registry.py` — `SkillRegistry` 不读盘，只合并多个 Provider；按名查找，同名时先注册的胜出。`catalog_text()` 把目录编成给模型看的列表。
- `filesystem.py` — `FilesystemSkillProvider`：从一个目录扫 `*.md` / `*.md.txt`，实现上面的协议。
- `frontmatter.py` — 解析文件开头 `---` 里的 `name` / `description`。
- `tool.py` — `make_skill_tool`：模型用的 `skill` 工具，按名从注册表取正文。
- `capability.py` — `SkillCapability`：把来源、工具、目录提示词一次接上。
