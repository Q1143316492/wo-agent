"""compose：按 Capability 组装；skill 目录进入 system_prompt，不进 session。"""

from pathlib import Path

from compaction import CompactionCapability, CompactionOptions
from compose import compose
from llm.types import TextBlock
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


def test_compose_passes_commands_slot():
    marker = object()
    ctx = compose(commands=marker)
    assert ctx.commands is marker
    assert compose().commands is None
