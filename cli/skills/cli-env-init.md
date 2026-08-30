---
name: cli-env-init
description: 初始化 wo-agent CLI 本机环境：问过用户之后，把 ripgrep 装到仓库里被 gitignore 的目录。
---

# CLI 环境初始化

有人指定本文件、要初始化 CLI 环境、或本机没有 `rg` 时，按下面做。只给步骤，不执行。

## 1. 先问

问用户：要不要把 ripgrep 安装到 `wo-agent/.vendor/rg/`（Windows 是这个目录里的 `rg.exe`）。

没答应就停：不下载、不改 PATH、不从别处拷贝。问就是对话里说一句，等用户下一轮回答。

## 2. 答应了再装

从 GitHub `BurntSushi/ripgrep` 的 Releases 按当前操作系统和 CPU 下载官方 zip 或 tarball，解压出 `rg` 或 `rg.exe`，放到 `wo-agent/.vendor/rg/`。

禁止复制 Cursor 或 VS Code 安装目录里的 `rg`。那是编辑器内部副本，不是这份 CLI 的安装物。

该目录已被 gitignore，不要把二进制提交进 git。

## 3. 装完告诉用户

下次在 `wo-agent` 下跑 `python -m cli` 时，会从 `.vendor/rg/` 找到 `rg`，工具表才会出现 `grep` 和 `glob`。也可以设环境变量 `WO_AGENT_RG` 指向别的可执行文件。
