"""公开的 Agent 契约。循环与扩展只对这个编程，绝不依赖具体驱动实现（dsh "无特权核心"）。

``followup`` / ``steer`` / ``inject`` / ``enqueue`` 都进 inbox；只有前两个唤醒驱动。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from session import Session

AgentStatus = Literal["idle", "running"]


@dataclass(frozen=True)
class AgentOptions:
    provider: str
    model: str
    max_tokens: int | None = None
    temperature: float | None = None
    max_retries: int = 3
    retry_backoff_s: float = 0.0


class Agent(Protocol):
    """The public live-agent handle."""

    id: str
    session: Session
    status: AgentStatus

    async def followup(self, text: str) -> None:
        """Enqueue a next-turn user message, wake the driver, wait until idle."""
        ...

    async def steer(self, text: str) -> None:
        """Enqueue a next-step user message and wake. Claimed at the next step boundary."""
        ...

    def inject(self, text: str) -> None:
        """Enqueue a next-step message without waking. Idle agents stay idle."""
        ...

    def enqueue(self, text: str) -> None:
        """Enqueue a next-turn message without waking. A running driver claims it after the current turn."""
        ...

    def queued(self) -> tuple[tuple[str, str], ...]:
        """Pending next-turn items as ``(id, text)``, oldest first."""
        ...

    def take_back(self) -> str | None:
        """Remove the newest queued next-turn message and return its text."""
        ...

    def cancel(self, cause: str, *, keep_inbox: bool = False) -> None:
        """Abort the active run. ``keep_inbox`` leaves queued next-turn messages."""
        ...

    async def when_idle(self) -> None:
        """Resolve after the current activity settles."""
        ...
