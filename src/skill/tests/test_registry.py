"""SkillRegistry：合并目录、先注册者胜出。"""

from skill.protocol import SkillDefinition, SkillSummary
from skill.registry import SkillRegistry, is_skill_name


class MemProvider:
    def __init__(self, name, skills):
        self.name = name
        self._skills = skills

    def list(self):
        return [
            SkillSummary(name=s["name"], description=s["description"], provider=self.name)
            for s in self._skills
        ]

    def get(self, skill_name):
        for s in self._skills:
            if s["name"] == skill_name:
                return SkillDefinition(
                    name=s["name"], description=s["description"],
                    provider=self.name, content=s["content"],
                )
        return None


def test_first_provider_wins_duplicate_names():
    registry = SkillRegistry()
    registry.add_provider(MemProvider("a", [{"name": "x", "description": "from-a", "content": "A"}]))
    registry.add_provider(MemProvider("b", [{"name": "x", "description": "from-b", "content": "B"}]))
    listed = registry.list()
    assert len(listed) == 1
    assert listed[0].description == "from-a"
    assert registry.get("x").content == "A"


def test_catalog_text_empty_when_no_skills():
    assert SkillRegistry().catalog_text() == ""


def test_catalog_text_lists_names():
    registry = SkillRegistry()
    registry.add_provider(MemProvider("a", [{"name": "identity", "description": "who", "content": ""}]))
    text = registry.catalog_text()
    assert "`identity`" in text
    assert "who" in text
    assert "<available_skills>" in text


def test_is_skill_name():
    assert is_skill_name("editor-ui")
    assert not is_skill_name("EditorUI")
    assert not is_skill_name("a/b")
