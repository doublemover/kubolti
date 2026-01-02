"""Cleanup helpers for build artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable


def supported_clean_targets() -> tuple[str, ...]:
    return (
        "normalized",
        "runner-logs",
        "dsf-validation",
        "xp12",
        "diagnostics",
        "metrics",
    )


def _unique(paths: Iterable[Path]) -> list[Path]:
    seen = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _resolve_paths(build_dir: Path, target: str) -> list[Path]:
    if target == "normalized":
        return [build_dir / "normalized"]
    if target == "runner-logs":
        return [build_dir / "runner_logs"]
    if target == "dsf-validation":
        return [build_dir / "dsf_validation"]
    if target == "xp12":
        return [build_dir / "xp12"]
    if target == "diagnostics":
        return list(build_dir.glob("diagnostics_*.zip"))
    if target == "metrics":
        paths: list[Path] = []
        metrics_path = build_dir / "metrics.json"
        if metrics_path.exists():
            paths.append(metrics_path)
        paths.extend(build_dir.glob("*.metrics.json"))
        return _unique(paths)
    raise ValueError(f"Unsupported clean target: {target}")


def clean_build(
    build_dir: Path,
    *,
    include: Iterable[str],
    dry_run: bool = True,
) -> dict[str, object]:
    """Clean build artifacts and return a summary report."""
    include_list = list(include)
    removed: dict[str, list[str]] = {}
    missing: dict[str, list[str]] = {}
    for target in include_list:
        paths = _resolve_paths(build_dir, target)
        removed[target] = []
        missing[target] = []
        for path in paths:
            if not path.exists():
                missing[target].append(str(path))
                continue
            removed[target].append(str(path))
            if dry_run:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
    return {
        "build_dir": str(build_dir),
        "dry_run": dry_run,
        "include": include_list,
        "removed": removed,
        "missing": missing,
    }


def format_clean_summary(report: dict[str, object]) -> list[str]:
    """Format a summary of clean results for logging."""
    build_dir = report.get("build_dir")
    dry_run = report.get("dry_run")
    include = report.get("include") or []
    removed = report.get("removed") or {}

    lines = [f"Clean {'dry-run' if dry_run else 'complete'} for {build_dir}"]
    for target in include:
        entries = removed.get(target, [])
        count = len(entries) if isinstance(entries, list) else 0
        lines.append(f"{target}: {count} item(s)")
    if dry_run:
        lines.append("Dry run only; re-run with --confirm to delete.")
    return lines
