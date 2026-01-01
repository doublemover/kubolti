from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


def _load_runner():
    return importlib.import_module("dem2dsf.runners.ortho4xp")


def test_runner_requires_root(tmp_path: Path, capsys, monkeypatch) -> None:
    module = _load_runner()
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ortho4xp_runner.py",
            "--tile",
            "+47+008",
            "--dem",
            str(dem_path),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    assert module.main() == 2
    output = capsys.readouterr().err
    assert "Ortho4XP root not provided" in output


def test_runner_missing_dem(tmp_path: Path, capsys, monkeypatch) -> None:
    module = _load_runner()
    ortho_root = tmp_path / "ortho"
    ortho_root.mkdir()
    script_path = ortho_root / "Ortho4XP_v140.py"
    script_path.write_text("pass", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ortho4xp_runner.py",
            "--tile",
            "+47+008",
            "--dem",
            str(tmp_path / "missing.tif"),
            "--output",
            str(tmp_path / "out"),
            "--ortho-root",
            str(ortho_root),
        ],
    )
    assert module.main() == 2
    output = capsys.readouterr().err
    assert "DEM path not found" in output


def test_runner_warns_on_version_mismatch(tmp_path: Path, capsys, monkeypatch) -> None:
    module = _load_runner()
    ortho_root = tmp_path / "ortho"
    ortho_root.mkdir()
    script_path = ortho_root / "Ortho4XP_v130.py"
    script_path.write_text("pass", encoding="utf-8")
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")

    monkeypatch.setattr(
        module,
        "probe_python_runtime",
        lambda *_: (sys.executable, (3, 13, 0), None),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ortho4xp_runner.py",
            "--tile",
            "+47+008",
            "--dem",
            str(dem_path),
            "--output",
            str(tmp_path / "out"),
            "--ortho-root",
            str(ortho_root),
            "--dry-run",
        ],
    )
    with pytest.warns(RuntimeWarning, match="Ortho4XP 1.30"):
        assert module.main() == 0
    output = capsys.readouterr().err
    assert "Ortho4XP 1.30 detected" in output


def test_run_with_config_restores_when_missing(tmp_path: Path, monkeypatch) -> None:
    module = _load_runner()
    config_path = tmp_path / "Ortho4XP.cfg"
    called = {"restored": False}

    def fake_patch(path: Path, _updates: dict[str, object]) -> str | None:
        path.write_text("patched", encoding="utf-8")
        return None

    def fake_restore(path: Path, original: str | None) -> None:
        assert path == config_path
        assert original is None
        called["restored"] = True

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["ortho"], 0, "", "")

    monkeypatch.setattr(module, "patch_config_values", fake_patch)
    monkeypatch.setattr(module, "restore_config", fake_restore)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._run_with_config(
        config_path=config_path,
        config_updates={"foo": "bar"},
        cmd=["ortho"],
        cwd=tmp_path,
        persist_config=False,
    )
    assert called["restored"] is True


def test_run_with_config_persists_when_requested(tmp_path: Path, monkeypatch) -> None:
    module = _load_runner()
    config_path = tmp_path / "Ortho4XP.cfg"
    called = {"restored": False}

    def fake_patch(path: Path, _updates: dict[str, object]) -> str | None:
        path.write_text("patched", encoding="utf-8")
        return None

    def fake_restore(*_args, **_kwargs) -> None:
        called["restored"] = True

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["ortho"], 0, "", "")

    monkeypatch.setattr(module, "patch_config_values", fake_patch)
    monkeypatch.setattr(module, "restore_config", fake_restore)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._run_with_config(
        config_path=config_path,
        config_updates={"foo": "bar"},
        cmd=["ortho"],
        cwd=tmp_path,
        persist_config=True,
    )
    assert called["restored"] is False


def test_parse_runner_events() -> None:
    module = _load_runner()
    stdout = "\n".join(
        [
            "Step 1: Assemble vector data",
            "Start of the mesh algorithm Triangle4XP",
            "Converted text DSF to binary DSF",
        ]
    )
    stderr = "\n".join(
        [
            "Downloading DEM tile",
            "Extracting overlay data",
        ]
    )
    events = module.parse_runner_events(stdout, stderr)
    assert any(event["event"] == "step" for event in events)
    assert any(event["event"] == "triangle4xp_start" for event in events)
    assert any(event["event"] == "dsf_compiled" for event in events)
    assert any(event["event"] == "download" for event in events)
    assert any(event["event"] == "overlay" for event in events)


def test_triangle_retry_helpers() -> None:
    module = _load_runner()
    assert module._retry_min_angles(None) == [5.0, 0.0]
    assert module._retry_min_angles(4.0) == [0.0]
    assert module._needs_triangulation_retry("Triangle4XP failed", "") is True
