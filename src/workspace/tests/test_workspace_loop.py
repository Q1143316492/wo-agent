"""组装后的循环能调工作区工具。"""

from pathlib import Path

from agent import AgentOptions, ReactLoopAgent
from compose import compose
from llm.types import BlockStart, FinishChunk, FinishReason, TextDelta, ToolCallDelta
from session import Session
from workspace import WorkspaceCapability


class FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def stream(self, request, signal=None):
        chunks = self._responses[self.calls]
        self.calls += 1
        for chunk in chunks:
            yield chunk


async def test_composed_write_then_read(tmp_path: Path):
    ctx = compose(WorkspaceCapability(tmp_path))
    session = Session()
    provider = FakeProvider(
        [
            [
                BlockStart(index=0, block_type="tool-call"),
                ToolCallDelta(
                    index=0,
                    id="c1",
                    name="write",
                    arguments_delta='{"file_path":"note.txt","content":"hi\\n"}',
                ),
                FinishChunk(reason=FinishReason(kind="tool-calls")),
            ],
            [
                BlockStart(index=0, block_type="text"),
                TextDelta(index=0, text="wrote"),
                FinishChunk(reason=FinishReason(kind="stop")),
            ],
        ]
    )
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), ctx.tools)
    await agent.followup("write a note")
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "hi\n"
    msgs = session.derive_messages()
    assert "Created file" in msgs[2].content[0].content[0].text
