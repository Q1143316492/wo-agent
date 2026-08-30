"""从 session 日志加总 token。不进循环、不另开 session-stats。"""

from __future__ import annotations

from llm.types import TokenUsage
from session import Session


def sum_usage(session: Session) -> TokenUsage:
    total = TokenUsage()
    for entry in session.events:
        event = entry.event
        if event.type != "assistant/message" or event.usage is None:
            continue
        u = event.usage
        total = TokenUsage(
            input=total.input + u.input,
            output=total.output + u.output,
            cache_read=total.cache_read + u.cache_read,
            cache_write=total.cache_write + u.cache_write,
            reasoning=total.reasoning + u.reasoning,
        )
    return total
