"""YAML frontmatter（开头 --- 块）的最小解析。

不引入 PyYAML：技能文件只用单行 ``name`` / ``description``，与 UTAgent
``loadSkill`` 的 md.txt 约定兼容。
"""

from __future__ import annotations


def parse_frontmatter(text: str) -> dict[str, str]:
    """解析开头 YAML frontmatter 的 name / description。无 frontmatter 返回空 dict。"""
    out: dict[str, str] = {}
    if not text.startswith("---"):
        return out
    end = text.find("---", 3)
    if end < 0:
        return out
    for line in text[3:end].splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key in ("name", "description") and val:
            out[key] = val
    return out
