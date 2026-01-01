from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from dem2dsf.tools.xptools_build import BuiltTool


def _load_script():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "build_xptools.py"
    spec = importlib.util.spec_from_file_location("build_xptools", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_xptools_script_writes_config(tmp_path: Path, monkeypatch) -> None:
    module = _load_script()
    dsftool = tmp_path / "DSFTool.exe"
    ddstool = tmp_path / "DDSTool.exe"
    for tool in (dsftool, ddstool):
        tool.write_text("bin", encoding="utf-8")

    monkeypatch.setattr(
        module,
        "build_xptools",
        lambda **_: [BuiltTool("dsftool", dsftool), BuiltTool("ddstool", ddstool)],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_xptools.py",
            "--root",
            str(tmp_path),
            "--write-config",
        ],
    )

    assert module.main() == 0
    assert (tmp_path / "tool_paths.json").exists()


def test_build_xptools_script_uses_existing_tools(tmp_path: Path, monkeypatch) -> None:
    module = _load_script()
    xptools_dir = tmp_path / "xptools"
    xptools_dir.mkdir()
    (xptools_dir / "DSFTool.exe").write_text("bin", encoding="utf-8")
    (xptools_dir / "DDSTool.exe").write_text("bin", encoding="utf-8")

    def boom(**_kwargs):
        raise AssertionError("build should not be called")

    monkeypatch.setattr(module, "build_xptools", boom)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_xptools.py",
            "--root",
            str(tmp_path),
            "--write-config",
        ],
    )

    assert module.main() == 0
    assert (tmp_path / "tool_paths.json").exists()
