from compose import compose
from system_prompt import AgentsMdCapability, SystemPromptCapability


def test_walks_up_and_includes_both_names(tmp_path):
    home = tmp_path / "home"
    proj = home / "proj"
    proj.mkdir(parents=True)
    (home / "AGENTS.md").write_text("home-agents", encoding="utf-8")
    (proj / "CLAUDE.md").write_text("proj-claude", encoding="utf-8")
    ctx = compose(
        SystemPromptCapability(identity="id"),
        AgentsMdCapability(root=proj, stop_at=home),
    )
    text = ctx.system_prompt.assemble()
    assert "home-agents" in text
    assert "proj-claude" in text
    assert text.index("home-agents") < text.index("proj-claude")


def test_missing_files_add_nothing(tmp_path):
    ctx = compose(AgentsMdCapability(root=tmp_path, stop_at=tmp_path))
    assert ctx.system_prompt.assemble() == ""
