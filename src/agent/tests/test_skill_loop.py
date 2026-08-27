"""组装后的循环：system 提示词只出现在请求里，不进 derive_messages。"""

from pathlib import Path

from agent import AgentOptions, ReactLoopAgent
from compose import compose
from llm.types import BlockStart, FinishChunk, FinishReason, TextDelta, ToolCallDelta
from session import Session
from skill import SkillCapability
from system_prompt import SystemPromptCapability

FIXTURES = Path(__file__).resolve().parents[2] / "skill" / "tests" / "fixtures"


class FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.requests = []

    async def stream(self, request, signal=None):
        self.requests.append(request)
        chunks = self._responses[self.calls]
        self.calls += 1
        for chunk in chunks:
            yield chunk


async def test_composed_skill_react_roundtrip():
    ctx = compose(SystemPromptCapability(identity="harness."), SkillCapability(FIXTURES))
    session = Session()
    provider = FakeProvider(
        [
            [
                BlockStart(index=0, block_type="tool-call"),
                ToolCallDelta(index=0, id="c1", name="skill", arguments_delta='{"name":"identity"}'),
                FinishChunk(reason=FinishReason(kind="tool-calls")),
            ],
            [
                BlockStart(index=0, block_type="text"),
                TextDelta(index=0, text="loaded"),
                FinishChunk(reason=FinishReason(kind="stop")),
            ],
        ]
    )
    agent = ReactLoopAgent(
        session,
        provider,
        AgentOptions(provider="fake", model="m"),
        ctx.tools,
        system_prompt=ctx.system_prompt,
    )
    await agent.followup("load identity")

    msgs = session.derive_messages()
    assert [m.role for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert "Fixture identity body" in msgs[2].content[0].content[0].text
    assert msgs[3].content[0].text == "loaded"

    first = provider.requests[0].messages[0]
    assert first.role == "system"
    assert first.source.kind == "plugin"
    assert "harness." in first.content[0].text
    assert "`identity`" in first.content[0].text
