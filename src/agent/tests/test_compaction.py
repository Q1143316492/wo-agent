"""循环在发请求前压缩；窗口溢出再压一次后重试该步。"""

from agent import AgentOptions, ReactLoopAgent
from compaction.engine import BasicCompaction, CompactionOptions
from llm.errors import CONTEXT_WINDOW_EXCEEDED
from llm.types import BlockStart, FinishChunk, FinishReason, LlmFailure, TextBlock, TextDelta, create_user_message
from session import Session
from session.events import UserMessageEvent
from tools import ToolResult
from compaction.summarizer import SUMMARY_OPEN_TAG

CHUNK = "abcdefghij" * 40


class FakeTools:
    def schemas(self):
        return []

    async def execute(self, name, arguments):
        return ToolResult(content=[TextBlock(text="ok")])


class ScriptedProvider:
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


def _text(text):
    return [
        BlockStart(index=0, block_type="text"),
        TextDelta(index=0, text=text),
        FinishChunk(reason=FinishReason(kind="stop")),
    ]


def _error(code):
    return [
        FinishChunk(reason=FinishReason(kind="error", failure=LlmFailure(message=code, code=code))),
    ]


class FakeSummarizer:
    async def summarize(self, messages, signal=None):
        return "EARLIER"


def _fill(session, n, text="abcdefghij"):
    for _ in range(n):
        session.append(UserMessageEvent(message=create_user_message([TextBlock(text=text)])))


async def test_loop_compacts_before_first_request():
    session = Session()
    _fill(session, 5, CHUNK)
    provider = ScriptedProvider([_text("ok")])
    engine = BasicCompaction(FakeSummarizer(), CompactionOptions(threshold_chars=40, retain_chars=900))
    agent = ReactLoopAgent(
        session, provider, AgentOptions(provider="fake", model="m"), FakeTools(), compaction=engine
    )
    await agent.followup("now")
    assert provider.calls == 1
    user_texts = [
        b.text
        for m in provider.requests[0].messages
        if m.role == "user"
        for b in m.content
        if b.type == "text"
    ]
    assert any(SUMMARY_OPEN_TAG in t for t in user_texts)
    assert CHUNK in user_texts  # 尾部保留
    assert any(e.event.type == "compaction/start" for e in session.events)


async def test_context_window_overflow_compacts_then_retries():
    session = Session()
    _fill(session, 5, CHUNK)
    provider = ScriptedProvider([_error(CONTEXT_WINDOW_EXCEEDED), _text("recovered")])
    engine = BasicCompaction(
        FakeSummarizer(),
        CompactionOptions(threshold_chars=10_000, retain_chars=900),
    )
    agent = ReactLoopAgent(
        session, provider, AgentOptions(provider="fake", model="m"), FakeTools(), compaction=engine
    )
    await agent.followup("go")
    assert provider.calls == 2
    assert session.events[-1].event.reason == "completed"
    assert any(SUMMARY_OPEN_TAG in m.content[0].text for m in session.derive_messages())
