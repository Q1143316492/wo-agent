This directory is the default fenced workspace root for `demo_agent.py`.

`read` / `write` / `edit` stay inside this folder. `bash` runs with this folder as cwd and is **not** sandboxed — it can reach paths outside.

Override with `WO_AGENT_WORKSPACE`. Windows needs Git Bash (or `bash.exe` on PATH).
