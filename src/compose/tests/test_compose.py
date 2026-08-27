"""compose：按 Capability 组装；skill 目录进入 system_prompt，不进 session。"""

from pathlib import Path

from agent import AgentOptions
from compaction import CompactionCapability, CompactionOptions
from compose import assemble, compose
from llm.types import TextBlock
from session import JsonlSessionStore, Session
from skill import SkillCapability
from system_prompt import SystemPromptCapability
from tools import ToolDefinition

FIXTURES = Path(__file__).resolve().parents[2] / "skill" / "tests" / "fixtures"


class EchoCapability:
    def mount(self, ctx):
        async def execute(args):
            return [TextBlock(text=args.get("text", ""))]

        ctx.tools.register(
            ToolDefinition(
                name="echo",
                description="echo",
                parameters={"type": "object", "properties": {"text": {"type": "string"}}},
                execute=execute,
            )
        )


def test_compose_mounts_each_capability():
    ctx = compose(EchoCapability(), SkillCapability(FIXTURES))
    names = {s.name for s in ctx.tools.schemas()}
    assert names == {"echo", "skill"}
    assert {s.name for s in ctx.skills.list()} == {"identity", "greeter"}


def test_omitting_skill_capability_has_no_skill_tool():
    ctx = compose(EchoCapability())
    assert [s.name for s in ctx.tools.schemas()] == ["echo"]
    assert ctx.skills.list() == []
    assert ctx.system_prompt.assemble() == ""
    assert ctx.compaction is None


def test_skill_catalog_lives_in_system_prompt():
    ctx = compose(SkillCapability(FIXTURES))
    text = ctx.system_prompt.assemble()
    assert "`identity`" in text
    assert "`greeter`" in text


def test_identity_section_precedes_catalog():
    ctx = compose(SystemPromptCapability(identity="I am wo-agent."), SkillCapability(FIXTURES))
    text = ctx.system_prompt.assemble()
    assert text.startswith("I am wo-agent.")
    assert "`identity`" in text


class _SilentSummarizer:
    async def summarize(self, messages, signal=None):
        return "x"


def test_compaction_capability_fills_slot():
    ctx = compose(CompactionCapability(_SilentSummarizer(), CompactionOptions(threshold_chars=100)))
    assert ctx.compaction is not None
    assert hasattr(ctx.compaction, "compact_if_needed")


class _NoopProvider:
    async def stream(self, request, signal=None):
        if False:
            yield None


def test_assemble_wires_session_and_tools():
    existing = Session()
    built = assemble(
        _NoopProvider(),
        [EchoCapability()],
        AgentOptions(provider="fake", model="m"),
        session=existing,
    )
    assert built.session is existing
    assert built.agent.session is existing
    assert {s.name for s in built.ctx.tools.schemas()} == {"echo"}


def test_assemble_loads_session_from_store(tmp_path):
    store = JsonlSessionStore(tmp_path)
    saved = Session()
    store.save(saved)
    built = assemble(
        _NoopProvider(),
        [EchoCapability()],
        AgentOptions(provider="fake", model="m"),
        store=store,
        session_id=saved.id,
    )
    assert built.session.id == saved.id


def test_assemble_wrap_tools_replaces_executor():
    wrapped = {}

    def wrap(inner):
        wrapped["inner"] = inner
        return inner

    built = assemble(
        _NoopProvider(),
        [EchoCapability()],
        AgentOptions(provider="fake", model="m"),
        wrap_tools=wrap,
    )
    assert wrapped["inner"] is built.ctx.tools


def test_assemble_blank_session_id_starts_new(tmp_path):
    store = JsonlSessionStore(tmp_path)
    built = assemble(
        _NoopProvider(),
        [EchoCapability()],
        AgentOptions(provider="fake", model="m"),
        store=store,
        session_id="  ",
    )
    assert built.session.id
    assert store.load(built.session.id) is None
