"""skill 工具：经注册表取正文；未知名走 is_error。"""

from pathlib import Path

from skill.filesystem import FilesystemSkillProvider
from skill.registry import SkillRegistry
from skill.tool import make_skill_tool
from tools import RegistryToolExecutor

FIXTURES = Path(__file__).parent / "fixtures"


def _executor():
    registry = SkillRegistry()
    registry.add_provider(FilesystemSkillProvider(FIXTURES))
    tools = RegistryToolExecutor()
    tools.register(make_skill_tool(registry))
    return tools


async def test_load_known_skill():
    result = await _executor().execute("skill", '{"name":"identity"}')
    assert result.is_error is False
    assert "Fixture identity body" in result.content[0].text


async def test_unknown_skill_is_error():
    result = await _executor().execute("skill", '{"name":"missing"}')
    assert result.is_error is True
    assert "not found" in result.content[0].text


async def test_invalid_name_is_error():
    result = await _executor().execute("skill", '{"name":"../x"}')
    assert result.is_error is True
