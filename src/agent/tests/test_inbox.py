"""inbox：inject 不唤醒；steer 进下一步；followup 排队下一轮。"""

import asyncio

from agent import AgentOptions, ReactLoopAgent
from agent.inbox import Inbox
from llm.types import BlockStart, FinishChunk, FinishReason, TextBlock, TextDelta, create_user_message
from session import Session
from tools import ToolResult


class FakeTools:
    def schemas(self):
        return []

    async def execute(self, name, arguments, cancel=None):
        return ToolResult(content=[TextBlock(text="ok")])


class SlowProvider:
    def __init__(self):
        self.requests = []
        self.gate = asyncio.Event()

    async def stream(self, request, signal=None):
        self.requests.append(request)
        if len(self.requests) == 1:
            await self.gate.wait()
        user_texts = [
            b.text
            for m in request.messages
            if m.role == "user"
            for b in m.content
            if getattr(b, "type", None) == "text"
        ]
        yield BlockStart(index=0, block_type="text")
        yield TextDelta(index=0, text="|".join(user_texts) or "ok")
        yield FinishChunk(reason=FinishReason(kind="stop"))


async def test_inject_while_idle_does_not_run():
    agent = ReactLoopAgent(Session(), SlowProvider(), AgentOptions(provider="fake", model="m"), FakeTools())
    agent.inject("secret")
    assert agent.status == "idle"
    assert agent.session.events == []


async def test_inject_joins_the_next_followup_step():
    session = Session()
    provider = SlowProvider()
    provider.gate.set()
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())
    agent.inject("ctx")
    await agent.followup("hi")
    users = [e.event.message.content[0].text for e in session.events if e.event.type == "user/message"]
    assert users == ["ctx", "hi"]


async def test_steer_is_claimed_at_next_step():
    session = Session()
    provider = SlowProvider()
    agent = ReactLoopAgent(session, provider, AgentOptions(provider="fake", model="m"), FakeTools())
    task = asyncio.create_task(agent.followup("first"))
    await asyncio.sleep(0.01)
    steered = asyncio.create_task(agent.steer("steer-me"))
    provider.gate.set()
    await task
    await steered
    users = [e.event.message.content[0].text for e in session.events if e.event.type == "user/message"]
    assert users == ["first", "steer-me"]
    assert len(provider.requests) == 2


def test_peek_turns_and_pop_last_turn():
    box = Inbox()
    a = create_user_message([TextBlock(text="a")])
    b = create_user_message([TextBlock(text="b")])
    box.push_turn(a)
    box.push_turn(b)
    assert box.peek_turns() == (a, b)
    assert box.pop_last_turn() is b
    assert box.peek_turns() == (a,)
    assert box.pop_last_turn() is a
    assert box.pop_last_turn() is None
