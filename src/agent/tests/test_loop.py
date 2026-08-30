"""ReactLoopAgent 测试——由 fake provider 驱动，不碰真实 LLM。

断言循环写进会话的持久事件序列：turn/step 边界、request/header 配置、
assistant 分片/消息，以及一次 ReAct step 的 tool/call -> tool/result 往返。
"""

import asyncio

from agent import AgentOptions, ReactLoopAgent
from llm.types import (
    BlockStart,
    FinishChunk,
    FinishReason,
    LlmFailure,
    TextBlock,
    TextDelta,
    ToolCallDelta,
)
from session import Session
from tools import RegistryToolExecutor, ToolDefinition, ToolResult


class FakeProvider:
    """每次 stream 调用按序吐一份固定分片序列。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.last_request = None

    async def stream(self, request, signal=None):
        self.last_request = request
        chunks = self._responses[self.calls]
        self.calls += 1
        for chunk in chunks:
            yield chunk


class FakeTools:
    def __init__(self):
        self.executed = []

    def schemas(self):
        return []

    async def execute(self, name, arguments, cancel=None):
        self.executed.append((name, arguments))
        return ToolResult(content=[TextBlock(text='{"ok": true}')])


def _tool_call_response():
    return [
        BlockStart(index=0, block_type="tool-call"),
        ToolCallDelta(index=0, id="c1", name="echo", arguments_delta='{"text":"hi"}'),
        FinishChunk(reason=FinishReason(kind="tool-calls")),
    ]


def _text_response(text):
    return [
        BlockStart(index=0, block_type="text"),
        TextDelta(index=0, text=text),
        FinishChunk(reason=FinishReason(kind="stop")),
    ]


def _event_types(session):
    return [e.event.type for e in session.events]


async def test_react_loop_full_flow():
    session = Session()
    provider = FakeProvider([_tool_call_response(), _text_response("echoed")])
    tools = FakeTools()
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), tools)

    await agent.followup("echo hi")

    # 持久事件序列：turn 先开，claim 后才落 user/message；工具属于该 step
    assert _event_types(session) == [
        "turn/start",
        "user/message",
        "step/start",
        "request/header",
        "assistant/chunk", "assistant/chunk", "assistant/chunk",
        "assistant/message",
        "tool/call",
        "tool/result",
        "step/end",
        "step/start",
        "request/header",
        "assistant/chunk", "assistant/chunk", "assistant/chunk",
        "assistant/message",
        "step/end",
        "turn/end",
    ]
    assert provider.calls == 2
    assert tools.executed == [("echo", '{"text":"hi"}')]


async def test_single_turn_no_tools():
    session = Session()
    provider = FakeProvider([_text_response("hi")])
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())

    await agent.followup("hello")

    assert _event_types(session) == [
        "turn/start",
        "user/message",
        "step/start",
        "request/header",
        "assistant/chunk", "assistant/chunk", "assistant/chunk",
        "assistant/message",
        "step/end",
        "turn/end",
    ]
    assert provider.calls == 1


async def test_request_header_recorded():
    session = Session()
    provider = FakeProvider([_tool_call_response(), _text_response("done")])
    agent = ReactLoopAgent(
        session, provider,
        AgentOptions(provider="deepseek", model="m", max_tokens=100, temperature=0.3),
        FakeTools(),
    )

    await agent.followup("x")

    headers = [e.event for e in session.events if e.event.type == "request/header"]
    assert len(headers) == 2
    assert headers[0].reason == "initial"
    assert headers[1].reason == "change"
    for h in headers:
        assert h.header.provider == "deepseek"
        assert h.header.model == "m"
        assert h.header.max_tokens == 100
        assert h.header.temperature == 0.3


async def test_derived_messages_after_react():
    session = Session()
    provider = FakeProvider([_tool_call_response(), _text_response("done")])
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())

    await agent.followup("echo hi")

    msgs = session.derive_messages()
    assert [m.role for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[1].content[0].type == "tool-call"
    assert msgs[2].content[0].type == "tool-result"
    assert msgs[2].content[0].tool_call_id == "c1"
    assert msgs[3].content[0].text == "done"


async def test_cancel_aborts_in_flight_stream():
    started = asyncio.Event()

    class HangProvider:
        async def stream(self, request, signal=None):
            started.set()
            if signal is not None:
                await signal.wait()
            yield FinishChunk(
                reason=FinishReason(kind="aborted", failure=LlmFailure(message="aborted", code="ABORTED"))
            )

    session = Session()
    agent = ReactLoopAgent(session, HangProvider(), AgentOptions(provider="fake", model="m"), FakeTools())
    task = asyncio.create_task(agent.followup("x"))
    await started.wait()
    agent.cancel("user")
    await asyncio.wait_for(task, timeout=1)
    assert agent.status == "idle"
    types = _event_types(session)
    assert types[0] == "turn/start"
    assert types[-1] == "turn/end"
    assert "assistant/message" not in types


async def test_cancel_aborts_in_flight_tool():
    started = asyncio.Event()

    class HangTools:
        def schemas(self):
            return []

        async def execute(self, name, arguments, cancel=None):
            started.set()
            if cancel is not None:
                await cancel.wait()
            return ToolResult(content=[TextBlock(text="late")])

    session = Session()
    provider = FakeProvider([_tool_call_response(), _text_response("nope")])
    agent = ReactLoopAgent(
        session, provider, AgentOptions(provider="fake", model="m"), HangTools()
    )
    task = asyncio.create_task(agent.followup("x"))
    await started.wait()
    agent.cancel("user", keep_inbox=True)
    await asyncio.wait_for(task, timeout=1)
    assert agent.status == "idle"
    assert provider.calls == 1
    texts = [
        e.event.message.content[0].content[0].text
        for e in session.events
        if e.event.type == "tool/result"
    ]
    assert texts == ["late"]
    ends = [e.event for e in session.events if e.event.type == "turn/end"]
    assert ends[-1].reason == "aborted"


async def test_status_lifecycle():
    session = Session()
    provider = FakeProvider([_text_response("hi")])
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())

    assert agent.status == "idle"
    await agent.followup("hi")
    assert agent.status == "idle"
    await agent.when_idle()  # 完成后立即返回


async def test_followup_while_running_queues_next_turn():
    class SlowProvider:
        def __init__(self):
            self.calls = 0

        async def stream(self, request, signal=None):
            self.calls += 1
            if self.calls == 1:
                await asyncio.sleep(0.05)
            yield BlockStart(index=0, block_type="text")
            yield TextDelta(index=0, text=f"r{self.calls}")
            yield FinishChunk(reason=FinishReason(kind="stop"))

    session = Session()
    provider = SlowProvider()
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())
    first = asyncio.create_task(agent.followup("x"))
    await asyncio.sleep(0.01)
    assert agent.status == "running"
    await agent.followup("y")
    await first

    users = [e.event.message.content[0].text for e in session.events if e.event.type == "user/message"]
    assert users == ["x", "y"]
    assert provider.calls == 2


async def test_enqueue_does_not_join_current_step():
    class SlowProvider:
        def __init__(self):
            self.calls = 0
            self.first_users: list[str] = []
            self.gate = asyncio.Event()

        async def stream(self, request, signal=None):
            self.calls += 1
            if self.calls == 1:
                self.first_users = [
                    b.text
                    for m in request.messages
                    if m.role == "user"
                    for b in m.content
                    if getattr(b, "type", None) == "text"
                ]
                await self.gate.wait()
            yield BlockStart(index=0, block_type="text")
            yield TextDelta(index=0, text=f"r{self.calls}")
            yield FinishChunk(reason=FinishReason(kind="stop"))

    session = Session()
    provider = SlowProvider()
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())
    task = asyncio.create_task(agent.followup("x"))
    await asyncio.sleep(0.01)
    agent.enqueue("y")
    assert [text for _, text in agent.queued()] == ["y"]
    provider.gate.set()
    await asyncio.wait_for(task, timeout=1)
    users = [e.event.message.content[0].text for e in session.events if e.event.type == "user/message"]
    assert users == ["x", "y"]
    assert "y" not in provider.first_users
    assert provider.calls == 2


def test_take_back_pops_newest_queued():
    agent = ReactLoopAgent(Session(), FakeProvider([]), AgentOptions(provider="fake", model="m"), FakeTools())
    agent.enqueue("a")
    agent.enqueue("b")
    assert agent.take_back() == "b"
    assert [text for _, text in agent.queued()] == ["a"]
    assert agent.take_back() == "a"
    assert agent.take_back() is None


async def test_cancel_keep_inbox_runs_queued_next():
    started = asyncio.Event()

    class HangThenOk:
        def __init__(self):
            self.calls = 0

        async def stream(self, request, signal=None):
            self.calls += 1
            if self.calls == 1:
                started.set()
                if signal is not None:
                    await signal.wait()
                yield FinishChunk(
                    reason=FinishReason(kind="aborted", failure=LlmFailure(message="aborted", code="ABORTED"))
                )
                return
            yield BlockStart(index=0, block_type="text")
            yield TextDelta(index=0, text="after")
            yield FinishChunk(reason=FinishReason(kind="stop"))

    session = Session()
    provider = HangThenOk()
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())
    task = asyncio.create_task(agent.followup("x"))
    await started.wait()
    agent.enqueue("y")
    agent.cancel("user", keep_inbox=True)
    await asyncio.wait_for(task, timeout=1)
    users = [e.event.message.content[0].text for e in session.events if e.event.type == "user/message"]
    assert users == ["x", "y"]
    assert provider.calls == 2
    assert agent.queued() == ()


async def test_cancel_drops_queue_by_default():
    started = asyncio.Event()

    class HangProvider:
        async def stream(self, request, signal=None):
            started.set()
            if signal is not None:
                await signal.wait()
            yield FinishChunk(
                reason=FinishReason(kind="aborted", failure=LlmFailure(message="aborted", code="ABORTED"))
            )

    session = Session()
    agent = ReactLoopAgent(session, HangProvider(), AgentOptions(provider="fake", model="m"), FakeTools())
    task = asyncio.create_task(agent.followup("x"))
    await started.wait()
    agent.enqueue("y")
    agent.cancel("user")
    await asyncio.wait_for(task, timeout=1)
    users = [e.event.message.content[0].text for e in session.events if e.event.type == "user/message"]
    assert users == ["x"]
    assert agent.queued() == ()


async def test_loop_sends_tool_schemas_in_request():
    class RecordingProvider:
        def __init__(self):
            self.requests = []
            self.calls = 0

        async def stream(self, request, signal=None):
            self.requests.append(request)
            if self.calls == 0:
                self.calls += 1
                yield BlockStart(index=0, block_type="tool-call")
                yield ToolCallDelta(index=0, id="c1", name="echo", arguments_delta='{"text":"hi"}')
                yield FinishChunk(reason=FinishReason(kind="tool-calls"))
            else:
                yield BlockStart(index=0, block_type="text")
                yield TextDelta(index=0, text="done")
                yield FinishChunk(reason=FinishReason(kind="stop"))

    async def echo(args):
        return [TextBlock(text=f"echoed: {args['text']}")]

    executor = RegistryToolExecutor()
    executor.register(ToolDefinition(name="echo", description="返回文本", parameters={}, execute=echo))

    provider = RecordingProvider()
    agent = ReactLoopAgent(Session(), provider, AgentOptions(provider="fake", model="m"), executor)
    await agent.followup("echo hi")

    # 第一次请求就带上工具的面向模型声明
    assert provider.requests[0].tools[0].name == "echo"
    # 工具真的被执行了（走 RegistryToolExecutor 管线）
    result = await executor.execute("echo", '{"text":"hi"}')
    assert result.content[0].text == "echoed: hi"
