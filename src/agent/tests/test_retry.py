"""request-error：可重试码在同一步再请求；不可重试码立刻结束。"""

from agent import AgentOptions, ReactLoopAgent
from llm.errors import AUTH, RATE_LIMIT, is_retryable
from llm.types import BlockStart, FinishChunk, FinishReason, LlmFailure, TextBlock, TextDelta
from session import Session
from tools import ToolResult


class FakeTools:
    def schemas(self):
        return []

    async def execute(self, name, arguments, cancel=None):
        return ToolResult(content=[TextBlock(text="ok")])


def _error(code):
    return [
        FinishChunk(reason=FinishReason(kind="error", failure=LlmFailure(message=code, code=code))),
    ]


def _text(text):
    return [
        BlockStart(index=0, block_type="text"),
        TextDelta(index=0, text=text),
        FinishChunk(reason=FinishReason(kind="stop")),
    ]


class ScriptedProvider:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def stream(self, request, signal=None):
        chunks = self._responses[self.calls]
        self.calls += 1
        for chunk in chunks:
            yield chunk


def test_is_retryable_codes():
    assert is_retryable(RATE_LIMIT)
    assert not is_retryable(AUTH)


async def test_rate_limit_retries_then_succeeds():
    session = Session()
    provider = ScriptedProvider([_error(RATE_LIMIT), _text("ok")])
    agent = ReactLoopAgent(
        session, provider,
        AgentOptions(provider="fake", model="m", max_retries=3),
        FakeTools(),
    )
    await agent.followup("hi")
    assert provider.calls == 2
    headers = [e.event for e in session.events if e.event.type == "request/header"]
    assert [h.reason for h in headers] == ["initial", "retry"]
    assert any(e.event.type == "assistant/message" for e in session.events)
    assert session.events[-1].event.reason == "completed"


async def test_auth_does_not_retry():
    session = Session()
    provider = ScriptedProvider([_error(AUTH)])
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())
    await agent.followup("hi")
    assert provider.calls == 1
    assert session.events[-1].event.reason == "error"
    assert not any(e.event.type == "assistant/message" for e in session.events)
