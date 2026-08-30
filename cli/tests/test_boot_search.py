"""CLI 只在找到 rg 时挂 SearchCapability。不调 boot()（要 API key）。"""

from pathlib import Path

from cli.boot import VENDOR_RG_DIR, cli_rg_path, cli_search_capability


def test_cli_rg_path_uses_vendor(tmp_path: Path, monkeypatch):
    vendor = tmp_path / "rg"
    vendor.mkdir()
    binary = vendor / "rg.exe"
    binary.write_bytes(b"x")
    monkeypatch.setattr("cli.boot.VENDOR_RG_DIR", vendor)
    monkeypatch.delenv("WO_AGENT_RG", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert cli_rg_path() == binary.resolve()


def test_cli_rg_path_none_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("cli.boot.VENDOR_RG_DIR", tmp_path / "nope")
    monkeypatch.delenv("WO_AGENT_RG", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert cli_rg_path() is None


def test_cli_search_capability_none_without_rg(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("cli.boot.VENDOR_RG_DIR", tmp_path / "nope")
    monkeypatch.delenv("WO_AGENT_RG", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert cli_search_capability(tmp_path) is None


def test_cli_search_capability_mounts_when_rg_found(tmp_path: Path, monkeypatch):
    vendor = tmp_path / "rg"
    vendor.mkdir()
    binary = vendor / "rg.exe"
    binary.write_bytes(b"x")
    monkeypatch.setattr("cli.boot.VENDOR_RG_DIR", vendor)
    monkeypatch.delenv("WO_AGENT_RG", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    cap = cli_search_capability(tmp_path)
    assert cap is not None
    from compose import compose

    ctx = compose(cap)
    assert {s.name for s in ctx.tools.schemas()} == {"grep", "glob"}
