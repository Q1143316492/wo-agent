from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_env_init_skill_asks_before_install():
    text = (ROOT / "skills" / "cli-env-init.md").read_text(encoding="utf-8")
    assert "cli-env-init" in text
    assert ".vendor/rg" in text
    assert "先问" in text or "是否" in text
    assert "Cursor" in text
