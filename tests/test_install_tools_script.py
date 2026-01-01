from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from dem2dsf.tools.installer import InstallResult


def _load_install_tools():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "install_tools.py"
    spec = importlib.util.spec_from_file_location("install_tools", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_install_tools_script_writes_config(monkeypatch, tmp_path: Path) -> None:
    module = _load_install_tools()
    stub_path = tmp_path / "tool"
    stub_path.write_text("stub", encoding="utf-8")

    def ok_result(name: str) -> InstallResult:
        return InstallResult(name, "ok", stub_path, "found")

    monkeypatch.setattr(module, "ensure_sevenzip", lambda: ok_result("7zip"))
    monkeypatch.setattr(
        module,
        "_ensure_ortho4xp",
        lambda *a, **k: ok_result("ortho4xp"),
    )
    monkeypatch.setattr(
        module,
        "_ensure_dsftool",
        lambda *a, **k: ok_result("dsftool"),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install_tools.py",
            "--check-only",
            "--non-interactive",
            "--write-config",
            "--root",
            str(tmp_path),
        ],
    )

    assert module.main() == 0
    assert (tmp_path / "tool_paths.json").exists()
