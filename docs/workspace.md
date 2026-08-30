# workspace

对应 `src/workspace/`。给模型一个围栏根：读、写、改 UTF-8 文本；可选本机 `bash`；可选本机 `rg` 做 `grep` / `glob`。不是核心层。循环不知道挂了哪几把刀。

```python
from compose import compose
from workspace import BashCapability, SearchCapability, WorkspaceCapability

ctx = compose(
    WorkspaceCapability(root),
    BashCapability(root),
    SearchCapability(root, rg_path="/usr/bin/rg"),  # 没有 rg 就不要挂这一条
)
ctx.tools.schemas()  # read / write / edit / bash / grep / glob
```

- `WorkspaceCapability(root)`：`read` / `write` / `edit`。相对路径相对该根解析，解析后必须仍在根下。
- `BashCapability(cwd)`：另挂。本机 spawn bash，围栏管不住命令。循环取消时杀掉进程树；已经取消则不再 spawn。结果 `aborted: true`，退出码 130。
- `SearchCapability(root, rg_path=...)`：另挂。`execute` 只 spawn 这份 `rg`，参数收成固定 argv。`grep` 搜内容，`glob` 用 `rg --files` 按名列文件。不自己实现匹配。单测可注入 `runner`，不必本机已装 `rg`。同样听取消。

CLI（`cli/boot.py`）按这个顺序找 `rg`，找到才挂 `SearchCapability`：

1. 环境变量 `WO_AGENT_RG`
2. `wo-agent/.vendor/rg/` 下的 `rg` / `rg.exe`（gitignore，不进包）
3. `PATH` 上的 `rg`

找不到工具表里就没有 `grep` / `glob`。说明书：`cli/skills/cli-env-init.md`（手动指定；先问用户再下载官方 ripgrep）。

## 文件

- `paths.py` — `WorkspacePaths.resolve`：围栏。
- `text.py` — 读写真改。
- `tools.py` — 面向模型的刀。
- `shell.py` — bash 起进程；取消或超时杀进程树。
- `search.py` — `resolve_rg`、argv、`LocalRipgrepRunner`。
- `capability.py` — 三条 Capability。
