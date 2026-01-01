from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script(name: str):
    module_path = Path(__file__).resolve().parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_gui_missing_pyinstaller(monkeypatch) -> None:
    module = _load_script("build_gui.py")
    monkeypatch.setattr(module, "_has_pyinstaller", lambda: False)
    assert module.main([]) == 2


def test_build_gui_entry_missing(monkeypatch, tmp_path: Path) -> None:
    module = _load_script("build_gui.py")
    monkeypatch.setattr(module, "_has_pyinstaller", lambda: True)
    missing_entry = tmp_path / "missing.py"
    assert module.main(["--entry", str(missing_entry)]) == 2


def test_build_gui_dry_run_command(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_script("build_gui.py")
    monkeypatch.setattr(module, "_has_pyinstaller", lambda: True)
    entry = tmp_path / "gui.py"
    entry.write_text("print('demo')", encoding="utf-8")
    result = module.main(
        [
            "--entry",
            str(entry),
            "--output-dir",
            str(tmp_path / "dist"),
            "--dry-run",
            "--console",
            "--onedir",
        ]
    )
    assert result == 0
    output = capsys.readouterr().out
    assert "--console" in output
    assert "--onedir" in output
    assert "--add-data" in output
    assert f"{module._data_separator()}scripts" in output


def test_build_gui_missing_runner_warns(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_script("build_gui.py")
    monkeypatch.setattr(module, "_has_pyinstaller", lambda: True)
    entry = tmp_path / "gui.py"
    entry.write_text("print('demo')", encoding="utf-8")
    missing_runner = tmp_path / "missing_runner.py"
    result = module.main(
        [
            "--entry",
            str(entry),
            "--dry-run",
            "--runner-path",
            str(missing_runner),
        ]
    )
    assert result == 0
    output = capsys.readouterr().out
    assert "Runner script not found" in output


def test_build_gui_default_icon_used(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_script("build_gui.py")
    root = tmp_path
    assets = root / "assets"
    assets.mkdir()
    icon_path = assets / "ballcow_icon.png"
    icon_path.write_text("stub", encoding="utf-8")
    entry = root / "src" / "dem2dsf" / "gui.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("print('demo')", encoding="utf-8")

    monkeypatch.setattr(module, "_default_repo_root", lambda: root)
    monkeypatch.setattr(module, "_has_pyinstaller", lambda: True)
    monkeypatch.setattr(module.sys, "platform", "linux", raising=False)
    result = module.main(["--entry", str(entry), "--dry-run", "--console", "--onedir"])
    assert result == 0
    output = capsys.readouterr().out
    assert "--icon" in output
    assert str(icon_path) in output


def test_build_gui_icon_unsupported(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_script("build_gui.py")
    entry = tmp_path / "gui.py"
    entry.write_text("print('demo')", encoding="utf-8")
    icon_path = tmp_path / "icon.png"
    icon_path.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(module, "_has_pyinstaller", lambda: True)
    monkeypatch.setattr(module, "_supports_png_icon", lambda: False)
    monkeypatch.setattr(module.sys, "platform", "win32", raising=False)
    result = module.main(
        ["--entry", str(entry), "--dry-run", "--icon", str(icon_path)]
    )
    assert result == 0
    output = capsys.readouterr().out
    assert "Icon format not supported" in output
