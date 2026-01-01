"""Diagnostics bundling helpers for build artifacts."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

DEFAULT_REPORTS = ("build_report.json", "build_plan.json")


def _collect_report_files(build_dir: Path) -> list[Path]:
    files = []
    for name in DEFAULT_REPORTS:
        candidate = build_dir / name
        if candidate.exists():
            files.append(candidate)
    return files


def _collect_metrics(build_dir: Path) -> list[Path]:
    matches: list[Path] = []
    for pattern in ("metrics.json", "*.metrics.json"):
        matches.extend(build_dir.rglob(pattern))
    return matches


def _collect_logs(build_dir: Path) -> list[Path]:
    log_dir = build_dir / "runner_logs"
    if not log_dir.exists():
        return []
    matches = list(log_dir.rglob("*.log"))
    matches.extend(log_dir.rglob("*.events.json"))
    return [path for path in matches if path.is_file()]


def _collect_profiles(profile_dir: Path) -> list[Path]:
    if not profile_dir.exists():
        return []
    results: list[Path] = []
    for pattern in ("*.pstats", "*.txt", "*.metrics.json"):
        results.extend(profile_dir.rglob(pattern))
    return results


def _unique(paths: list[Path], *, exclude: Path | None = None) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if exclude and resolved == exclude.resolve():
            continue
        if resolved in seen:
            continue
        if not path.exists():
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _arcname(path: Path, *, build_dir: Path, profile_dir: Path) -> str:
    try:
        return path.relative_to(build_dir).as_posix()
    except ValueError:
        pass
    try:
        return (Path("profiles") / path.relative_to(profile_dir)).as_posix()
    except ValueError:
        return path.name


def default_profile_dir() -> Path:
    """Return the default profile directory."""
    return Path(os.environ.get("DEM2DSF_PROFILE_DIR", "profiles")).expanduser()


def default_bundle_path(build_dir: Path) -> Path:
    """Return the default diagnostics bundle path for a build directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return build_dir / f"diagnostics_{timestamp}.zip"


def bundle_diagnostics(
    build_dir: Path,
    *,
    output_path: Path | None = None,
    metrics: list[Path] | None = None,
    profile_dir: Path | None = None,
    include_profiles: bool = True,
    include_logs: bool = True,
) -> Path | None:
    """Bundle diagnostics artifacts into a zip and return the archive path."""
    if not build_dir.exists():
        raise FileNotFoundError(f"Build directory not found: {build_dir}")

    if output_path is None:
        output_path = default_bundle_path(build_dir)

    paths: list[Path] = []
    paths.extend(_collect_report_files(build_dir))
    paths.extend(_collect_metrics(build_dir))
    if metrics:
        paths.extend([path.expanduser() for path in metrics])
    if include_logs:
        paths.extend(_collect_logs(build_dir))

    resolved_profile_dir = profile_dir.expanduser() if profile_dir else default_profile_dir()
    if include_profiles:
        paths.extend(_collect_profiles(resolved_profile_dir))

    paths = _unique(paths, exclude=output_path)
    if not paths:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(
                path,
                _arcname(path, build_dir=build_dir, profile_dir=resolved_profile_dir),
            )
    return output_path
