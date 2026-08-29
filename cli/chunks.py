"""把循环的 ``StreamChunk`` 收成 UI 事件。TTY 细节留在 ``cli.tui``，这里不碰 Textual。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from llm.types import FinishChunk, ReasoningDelta, StreamChunk, TextDelta, ToolCallDelta

UiKind = Literal["text", "think", "tool", "error"]


@dataclass(frozen=True)
class UiEvent:
    kind: UiKind
    text: str


def to_ui_event(chunk: StreamChunk) -> UiEvent | None:
    if isinstance(chunk, TextDelta) and chunk.text:
        return UiEvent("text", chunk.text)
    if isinstance(chunk, ReasoningDelta) and chunk.text:
        return UiEvent("think", chunk.text)
    if isinstance(chunk, ToolCallDelta) and chunk.name:
        return UiEvent("tool", chunk.name)
    if isinstance(chunk, FinishChunk) and chunk.reason.kind == "error":
        failure = chunk.reason.failure
        code = failure.code if failure else "?"
        message = failure.message if failure else ""
        return UiEvent("error", f"{code}: {message}")
    return None
