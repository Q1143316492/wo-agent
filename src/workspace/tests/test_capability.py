"""WorkspaceCapability：挂工具与提示词；省略则没有。"""

from pathlib import Path

from compose import compose
from skill import SkillCapability
from workspace import WorkspaceCapability

FIXTURES = Path(__file__).resolve().parents[2] / "skill" / "tests" / "fixtures"


def test_mount_registers_three_tools(tmp_path: Path):
    ctx = compose(WorkspaceCapability(tmp_path))
    assert {s.name for s in ctx.tools.schemas()} == {"read", "write", "edit"}
    text = ctx.system_prompt.assemble()
    assert "Workspace root:" in text
    assert "old_string" in text


def test_omitting_workspace_has_no_file_tools():
    ctx = compose(SkillCapability(FIXTURES))
    names = {s.name for s in ctx.tools.schemas()}
    assert names == {"skill"}
    assert "Workspace root:" not in ctx.system_prompt.assemble()
