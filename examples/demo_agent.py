"""终端里跑一轮真实的 ReAct agent。

组装：``assemble(provider, [SystemPrompt, Skill, Workspace, Bash, Compaction], options=...)``。
循环不知道 skill / 工作区 / bash / compaction。工作区根默认 ``examples/sandbox/``，可用 ``WO_AGENT_WORKSPACE`` 覆盖。
Windows 需要 Git Bash（或 PATH 上的 bash.exe）。
需要 ``UTAGENT_API_KEY`` 或 ``DEEPSEEK_API_KEY``。续跑设 ``WO_AGENT_SESSION`` 为已有 session id。

运行：.venv/Scripts/python examples/demo_agent.py
输入 /quit 退出。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 未 pip install -e 时也能 import src/ 下的包。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent import AgentOptions
from compose import assemble
from compaction import CompactionCapability, LlmSummarizer
from llm.deepseek import DeepSeekConfig, DeepSeekProvider
from llm.types import FinishChunk, ReasoningDelta, TextDelta, ToolCallDelta
from session import JsonlSessionStore
from skill import SkillCapability
from system_prompt import SystemPromptCapability
from workspace import BashCapability, WorkspaceCapability

SKILLS_DIR = Path(__file__).parent / "skills"
SESSIONS_DIR = Path(__file__).parent / ".sessions"
DEFAULT_WORKSPACE = Path(__file__).parent / "sandbox"


def _on_chunk(chunk) -> None:
    if isinstance(chunk, TextDelta):
        print(chunk.text, end="", flush=True)
    elif isinstance(chunk, ReasoningDelta):
        print(f"\n[think] {chunk.text}", end="", flush=True)
    elif isinstance(chunk, ToolCallDelta) and chunk.name:
        print(f"\n[tool] {chunk.name}", flush=True)
    elif isinstance(chunk, FinishChunk) and chunk.reason.kind == "error":
        failure = chunk.reason.failure
        code = failure.code if failure else "?"
        message = failure.message if failure else ""
        print(f"\n[error] {code}: {message}", flush=True)


async def main() -> None:
    key = os.environ.get("UTAGENT_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or ""
    if not key:
        print("set UTAGENT_API_KEY or DEEPSEEK_API_KEY")
        return

    provider = DeepSeekProvider(
        DeepSeekConfig(api_key=key, base_url="https://api.deepseek.com", model="deepseek-v4-flash")
    )
    workspace_root = Path(os.environ.get("WO_AGENT_WORKSPACE") or DEFAULT_WORKSPACE)
    store = JsonlSessionStore(SESSIONS_DIR)
    resume_id = os.environ.get("WO_AGENT_SESSION")
    session = store.load(resume_id) if resume_id else None
    if resume_id and session is None:
        print(f"session not found: {resume_id}")
        return

    built = assemble(
        provider,
        (
            SystemPromptCapability(),
            SkillCapability(SKILLS_DIR),
            WorkspaceCapability(workspace_root),
            BashCapability(workspace_root),
            CompactionCapability(
                LlmSummarizer(provider, provider_name="deepseek", model="deepseek-v4-flash")
            ),
        ),
        AgentOptions(provider="deepseek", model="deepseek-v4-flash", max_tokens=1024, retry_backoff_s=0.5),
        session=session,
        on_chunk=_on_chunk,
    )
    ctx, session, agent = built.ctx, built.session, built.agent

    print(f"session {session.id}  →  {SESSIONS_DIR / (session.id + '.jsonl')}")
    print(f"workspace {workspace_root.resolve()}")
    print("tools:", ", ".join(s.name for s in ctx.tools.schemas()) or "(none)")
    print("skills:", ", ".join(s.name for s in ctx.skills.list()) or "(none)")
    print("输入 /quit 退出\n")

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line in {"/quit", "/exit"}:
            break
        if not line:
            continue
        print("agent> ", end="", flush=True)
        await agent.followup(line)
        print()
        store.save(session)


if __name__ == "__main__":
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONUTF8", "1")
    asyncio.run(main())
