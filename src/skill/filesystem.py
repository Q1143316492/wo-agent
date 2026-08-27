"""本地目录技能源（dsh ``skill-filesystem``）。

扫描 ``*.md`` 与 ``*.md.txt``（后者兼容 UTAgent）。名字取 frontmatter 的
``name``，缺省则用文件名（去掉后缀）。只接受 kebab-case 名，拒绝路径穿越。
"""

from __future__ import annotations

from pathlib import Path

from .frontmatter import parse_frontmatter
from .protocol import SkillDefinition, SkillSummary
from .registry import is_skill_name


def _skill_id_from_filename(name: str) -> str | None:
    lower = name.lower()
    if lower.endswith(".md.txt"):
        stem = name[: -len(".md.txt")]
    elif lower.endswith(".md"):
        stem = name[: -len(".md")]
    else:
        return None
    return stem if is_skill_name(stem) else None


class FilesystemSkillProvider:
    def __init__(self, directory: str | Path, provider_name: str = "filesystem") -> None:
        self._dir = Path(directory)
        self.name = provider_name

    def _iter_files(self) -> list[tuple[str, Path]]:
        if not self._dir.is_dir():
            return []
        found: list[tuple[str, Path]] = []
        for path in sorted(self._dir.iterdir()):
            if not path.is_file():
                continue
            skill_id = _skill_id_from_filename(path.name)
            if skill_id is None:
                continue
            found.append((skill_id, path))
        return found

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def list(self) -> list[SkillSummary]:
        summaries: list[SkillSummary] = []
        seen: set[str] = set()
        for skill_id, path in self._iter_files():
            text = self._read(path)
            meta = parse_frontmatter(text)
            name = meta.get("name") or skill_id
            if not is_skill_name(name) or name in seen:
                continue
            seen.add(name)
            summaries.append(
                SkillSummary(
                    name=name,
                    description=meta.get("description", ""),
                    provider=self.name,
                )
            )
        return summaries

    def get(self, skill_name: str) -> SkillDefinition | None:
        if not is_skill_name(skill_name):
            return None
        for skill_id, path in self._iter_files():
            text = self._read(path)
            meta = parse_frontmatter(text)
            name = meta.get("name") or skill_id
            if name != skill_name:
                continue
            return SkillDefinition(
                name=name,
                description=meta.get("description", ""),
                provider=self.name,
                content=text,
            )
        return None
