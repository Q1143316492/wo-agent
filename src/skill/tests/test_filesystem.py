"""FilesystemSkillProvider：读夹具目录。"""

from pathlib import Path

from skill.filesystem import FilesystemSkillProvider

FIXTURES = Path(__file__).parent / "fixtures"


def test_lists_md_and_md_txt():
    provider = FilesystemSkillProvider(FIXTURES)
    names = {s.name for s in provider.list()}
    assert names == {"identity", "greeter"}


def test_get_returns_body():
    provider = FilesystemSkillProvider(FIXTURES)
    found = provider.get("identity")
    assert found is not None
    assert "Fixture identity body" in found.content
    assert found.provider == "filesystem"


def test_unknown_name_is_none():
    assert FilesystemSkillProvider(FIXTURES).get("missing") is None


def test_path_traversal_name_rejected():
    assert FilesystemSkillProvider(FIXTURES).get("../identity") is None
