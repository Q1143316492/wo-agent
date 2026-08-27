"""frontmatter 解析。"""

from skill.frontmatter import parse_frontmatter


def test_parses_name_and_description():
    text = '---\nname: identity\ndescription: "hello there"\n---\n\nbody\n'
    assert parse_frontmatter(text) == {"name": "identity", "description": "hello there"}


def test_missing_frontmatter_is_empty():
    assert parse_frontmatter("# just a title\n") == {}
