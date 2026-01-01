from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from zipfile import ZipFile


def _load_bundle():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "bundle_diagnostics.py"
    spec = importlib.util.spec_from_file_location("bundle_diagnostics", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_bundle_diagnostics_writes_zip(tmp_path: Path, monkeypatch) -> None:
    module = _load_bundle()
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "build_report.json").write_text("{}", encoding="utf-8")
    (build_dir / "build_plan.json").write_text("{}", encoding="utf-8")
    (build_dir / "metrics.json").write_text("{}", encoding="utf-8")
    log_dir = build_dir / "runner_logs"
    log_dir.mkdir()
    (log_dir / "ortho.stdout.log").write_text("log", encoding="utf-8")
    (log_dir / "ortho.events.json").write_text("[]", encoding="utf-8")

    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "build_demo.metrics.json").write_text("{}", encoding="utf-8")
    (profile_dir / "build_demo.pstats").write_text("stats", encoding="utf-8")

    output = tmp_path / "bundle.zip"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bundle_diagnostics.py",
            "--build-dir",
            str(build_dir),
            "--output",
            str(output),
            "--profile-dir",
            str(profile_dir),
        ],
    )

    assert module.main() == 0
    assert output.exists()
    with ZipFile(output) as archive:
        names = set(archive.namelist())
    assert "build_report.json" in names
    assert "build_plan.json" in names
    assert "metrics.json" in names
    assert "runner_logs/ortho.stdout.log" in names
    assert "runner_logs/ortho.events.json" in names
    assert "profiles/build_demo.metrics.json" in names
    assert "profiles/build_demo.pstats" in names


def test_bundle_diagnostics_no_files(tmp_path: Path, monkeypatch) -> None:
    module = _load_bundle()
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    output = tmp_path / "bundle.zip"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bundle_diagnostics.py",
            "--build-dir",
            str(build_dir),
            "--output",
            str(output),
        ],
    )

    assert module.main() == 1
    assert not output.exists()
