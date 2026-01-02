from __future__ import annotations

from pathlib import Path
from typing import Any

from dem2dsf.clean import clean_build, format_clean_summary


def test_clean_build_dry_run(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    target = build_dir / "normalized"
    target.mkdir(parents=True)

    report = clean_build(build_dir, include=["normalized"], dry_run=True)

    assert target.exists()
    assert report["dry_run"] is True
    assert report["removed"]["normalized"]


def test_clean_build_removes(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    target = build_dir / "runner_logs"
    target.mkdir(parents=True)

    report = clean_build(build_dir, include=["runner-logs"], dry_run=False)

    assert not target.exists()
    assert report["dry_run"] is False
    assert report["removed"]["runner-logs"]


def test_clean_summary_formats(tmp_path: Path) -> None:
    report: dict[str, Any] = {
        "build_dir": str(tmp_path),
        "dry_run": True,
        "include": ["normalized"],
        "removed": {"normalized": [str(tmp_path / "normalized")]},
    }
    lines = format_clean_summary(report)
    assert any("dry-run" in line for line in lines)
