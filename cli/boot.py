"""产品组装：选哪些 Capability、哪个 Provider、会话落哪。不进循环、不进 ``src/``。"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agent import AgentOptions, ReactLoopAgent
from compaction import CompactionCapability, LlmSummarizer
from compose import ComposeContext, assemble
from llm.deepseek import DeepSeekConfig, DeepSeekProvider
from llm.types import StreamChunk
from session import JsonlSessionStore, Session
from skill import SkillCapability
from system_prompt import SystemPromptCapability
from workspace import BashCapability, WorkspaceCapability

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
MODEL = "deepseek-v4-flash"


@dataclass
class Booted:
    ctx: ComposeContext
    session: Session
    agent: ReactLoopAgent
    store: JsonlSessionStore
    workspace: Path
    sessions_dir: Path


def api_key() -> str:
    return os.environ.get("UTAGENT_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or ""


def boot(on_chunk: Callable[[StreamChunk], None]) -> Booted:
    key = api_key()
    if not key:
        raise RuntimeError("set UTAGENT_API_KEY or DEEPSEEK_API_KEY")

    provider = DeepSeekProvider(
        DeepSeekConfig(api_key=key, base_url="https://api.deepseek.com", model=MODEL)
    )
    workspace = Path(os.environ.get("WO_AGENT_WORKSPACE") or Path.cwd()).resolve()
    sessions_dir = Path(os.environ.get("WO_AGENT_SESSIONS") or (Path.cwd() / ".wo-sessions"))
    store = JsonlSessionStore(sessions_dir)
    resume_id = os.environ.get("WO_AGENT_SESSION")
    session = store.load(resume_id) if resume_id else None
    if resume_id and session is None:
        raise RuntimeError(f"session not found: {resume_id}")

    built = assemble(
        provider,
        (
            SystemPromptCapability(),
            SkillCapability(SKILLS_DIR),
            WorkspaceCapability(workspace),
            BashCapability(workspace),
            CompactionCapability(LlmSummarizer(provider, provider_name="deepseek", model=MODEL)),
        ),
        AgentOptions(provider="deepseek", model=MODEL, max_tokens=1024, retry_backoff_s=0.5),
        session=session,
        on_chunk=on_chunk,
    )
    return Booted(
        ctx=built.ctx,
        session=built.session,
        agent=built.agent,
        store=store,
        workspace=workspace,
        sessions_dir=sessions_dir,
    )
