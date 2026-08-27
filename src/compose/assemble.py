"""宿主组装入口：compose + session + 循环。

嵌入方不必手拼 ``ReactLoopAgent``。循环仍无特权：本模块只接线，不选择
能力、不写 Unity / bash。产品 CLI、provider 工厂仍是后话，不要把这里收成
上帝类。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agent import AgentOptions, ReactLoopAgent
from llm.protocol import LLMProvider
from llm.types import StreamChunk
from session import Session, SessionStore
from tools import ToolExecutor

from .compose import Capability, ComposeContext, compose


@dataclass
class Assembled:
    """一次 ``assemble`` 的结果。``store`` 仍由调用方 save。"""

    ctx: ComposeContext
    session: Session
    agent: ReactLoopAgent


def assemble(
    provider: LLMProvider,
    capabilities: list[Capability] | tuple[Capability, ...],
    options: AgentOptions,
    *,
    session: Session | None = None,
    store: SessionStore | None = None,
    session_id: str | None = None,
    tools: ToolExecutor | None = None,
    wrap_tools: Callable[[ToolExecutor], ToolExecutor] | None = None,
    on_chunk: Callable[[StreamChunk], None] | None = None,
) -> Assembled:
    """按名单挂载能力，接上已有或新建的 session 与循环。

    ``session`` 优先；否则 ``store.load(session_id)``；再否则新建。
    ``tools`` 默认为 ``ctx.tools``。``wrap_tools`` 给宿主包一层（例如写 UI 流），
    不改循环、不进 Capability 名单。
    """
    ctx = compose(*capabilities)
    if session is None:
        sid = (session_id or "").strip()
        if store is not None and sid:
            session = store.load(sid)
        if session is None:
            session = Session()
    executor = tools if tools is not None else ctx.tools
    if wrap_tools is not None:
        executor = wrap_tools(executor)
    agent = ReactLoopAgent(
        session,
        provider,
        options,
        executor,
        system_prompt=ctx.system_prompt,
        compaction=ctx.compaction,
        on_chunk=on_chunk,
    )
    return Assembled(ctx=ctx, session=session, agent=agent)
