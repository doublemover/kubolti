"""Publish build artifacts and optional 7z compression."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PosixPath
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile

PUBLISH_MODES = ("full", "scenery")
SCENERY_DIRS = ("Earth nav data", "terrain", "textures")
SCENERY_FILES = ("library.txt", "library.dat", "library.xml")
REPORT_FILES = ("build_plan.json", "build_report.json")
SCENERY_EXCLUDE_SUFFIXES = (".uncompressed",)


def _utc_now() -> str:
    """Return the current UTC timestamp as ISO8601."""
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    """Compute the SHA-256 hash for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sevenzip_command(sevenzip_path: Path) -> list[str]:
    """Return the command prefix for running 7z."""
    if sevenzip_path.suffix.lower() == ".py":
        return [sys.executable, str(sevenzip_path)]
    return [str(sevenzip_path)]


def _safe_path(value: str) -> Path:
    """Return a Path that is stable even when os.name is monkeypatched."""
    if sys.platform != "win32":
        return PosixPath(value)
    return Path(value)


def find_sevenzip(explicit_path: Path | None = None) -> Path | None:
    """Locate a 7z executable from an explicit path, PATH, or common locations."""
    if explicit_path:
        return explicit_path if explicit_path.exists() else None
    which = shutil.which("7z")
    if which:
        return Path(which)
    candidates: Iterable[Path]
    if os.name == "nt":
        candidates = [
            _safe_path(os.environ.get("ProgramFiles", "C:/Program Files")) / "7-Zip" / "7z.exe",
            _safe_path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
            / "7-Zip"
            / "7z.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [Path("/opt/homebrew/bin/7z"), Path("/usr/local/bin/7z")]
    else:
        candidates = [Path("/usr/bin/7z"), Path("/usr/local/bin/7z")]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _compress_dsf_archives(
    sevenzip_path: Path,
    dsf_paths: Iterable[Path],
    *,
    keep_backup: bool = False,
) -> list[str]:
    """Compress DSF files with 7z and return error messages."""
    errors: list[str] = []
    command_prefix = _sevenzip_command(sevenzip_path)
    for dsf_path in dsf_paths:
        archive_path = dsf_path.with_name(f"{dsf_path.name}.7z")
        if archive_path.exists():
            archive_path.unlink()
        backup_path = dsf_path.with_suffix(f"{dsf_path.suffix}.uncompressed")
        result = subprocess.run(
            [
                *command_prefix,
                "a",
                "-t7z",
                "-mx=9",
                "-y",
                str(archive_path),
                dsf_path.name,
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=dsf_path.parent,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "7z failed"
            errors.append(f"{dsf_path}: {detail}")
            continue
        if keep_backup and not backup_path.exists():
            shutil.copy(dsf_path, backup_path)
        try:
            archive_path.replace(dsf_path)
        except OSError as exc:
            errors.append(f"{dsf_path}: failed to replace DSF: {exc}")
    return errors


def _sevenzip_version(sevenzip_path: Path | None) -> str | None:
    if not sevenzip_path:
        return None
    command_prefix = _sevenzip_command(sevenzip_path)
    for args in (command_prefix + ["-version"], command_prefix + ["--version"], command_prefix):
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        output = (result.stdout or result.stderr).strip()
        if output:
            return output.splitlines()[0].strip() or None
    return None


def _collect_publish_files(
    build_dir: Path,
    *,
    mode: str,
    warnings: list[str],
) -> list[Path]:
    if mode == "full":
        return sorted(path for path in build_dir.rglob("*") if path.is_file())
    if mode != "scenery":
        raise ValueError(f"Unknown publish mode: {mode}")
    files: set[Path] = set()
    for name in SCENERY_DIRS:
        root = build_dir / name
        if root.exists():
            files.update(path for path in root.rglob("*") if path.is_file())
        elif name == "Earth nav data":
            warnings.append("Earth nav data folder missing; scenery output may be incomplete.")
    for name in SCENERY_FILES + REPORT_FILES:
        candidate = build_dir / name
        if candidate.exists():
            files.add(candidate)
        elif name in REPORT_FILES:
            warnings.append(f"Missing report file: {name}.")
    filtered: list[Path] = []
    for path in files:
        if path.suffix in SCENERY_EXCLUDE_SUFFIXES:
            continue
        filtered.append(path)
    return sorted(filtered)


def publish_build(
    build_dir: Path,
    output_zip: Path,
    *,
    mode: str = "full",
    dsf_7z: bool = False,
    dsf_7z_backup: bool = False,
    sevenzip_path: Path | None = None,
    allow_missing_sevenzip: bool = False,
) -> dict[str, Any]:
    """Package build outputs into a zip with manifest and audit report."""
    if not build_dir.exists():
        raise FileNotFoundError(f"Build directory not found: {build_dir}")

    warnings: list[str] = []
    if mode not in PUBLISH_MODES:
        raise ValueError(f"Unsupported publish mode: {mode}")

    dsf_paths = sorted(path for path in build_dir.rglob("*.dsf") if path.is_file())
    dsf_7z_count = 0
    sevenzip_used: Path | None = None
    if dsf_7z:
        sevenzip_used = find_sevenzip(sevenzip_path)
        if not sevenzip_used:
            message = "7z not found; DSF compression skipped."
            if allow_missing_sevenzip:
                warnings.append(message)
            else:
                raise FileNotFoundError("7z not found; pass --sevenzip-path or allow fallback.")
        else:
            errors = _compress_dsf_archives(
                sevenzip_used,
                dsf_paths,
                keep_backup=dsf_7z_backup,
            )
            if errors:
                raise RuntimeError("7z compression failed: " + "; ".join(errors))
            dsf_7z_count = len(dsf_paths)

    publish_files = _collect_publish_files(build_dir, mode=mode, warnings=warnings)

    files: list[dict[str, Any]] = []
    total_bytes = 0
    for file_path in publish_files:
        rel_path = file_path.relative_to(build_dir)
        size = file_path.stat().st_size
        total_bytes += size
        files.append(
            {
                "path": str(rel_path),
                "size": size,
                "sha256": _sha256(file_path),
            }
        )

    tool_versions = {
        "sevenzip": _sevenzip_version(sevenzip_used),
    }
    dsf_count = len([path for path in publish_files if path.suffix == ".dsf"])

    manifest = {
        "created_at": _utc_now(),
        "build_dir": str(build_dir),
        "publish_mode": mode,
        "tool_versions": tool_versions,
        "dsf_7z": {
            "enabled": bool(dsf_7z and sevenzip_used),
            "count": dsf_7z_count,
            "backup": bool(dsf_7z_backup),
            "backup_suffix": ".uncompressed" if dsf_7z_backup else None,
        },
        "files": files,
    }
    manifest_path = build_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    audit = {
        "created_at": _utc_now(),
        "build_dir": str(build_dir),
        "publish_mode": mode,
        "total_files": len(files),
        "total_bytes": total_bytes,
        "dsf_count": dsf_count,
        "tool_versions": tool_versions,
        "dsf_7z": {
            "enabled": bool(dsf_7z and sevenzip_used),
            "count": dsf_7z_count,
            "sevenzip_path": str(sevenzip_used) if sevenzip_used else None,
            "sevenzip_version": tool_versions.get("sevenzip"),
            "backup": bool(dsf_7z_backup),
            "backup_suffix": ".uncompressed" if dsf_7z_backup else None,
            "warnings": warnings,
        },
    }
    audit_path = build_dir / "audit_report.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    package_files = list(publish_files)
    package_files.extend([manifest_path, audit_path])
    package_files = sorted({path.resolve(): path for path in package_files}.values())
    package_files = [path for path in package_files if path.exists()]

    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in package_files:
            archive.write(file_path, file_path.relative_to(build_dir))

    return {
        "zip_path": str(output_zip),
        "manifest_path": str(manifest_path),
        "audit_report_path": str(audit_path),
        "warnings": warnings,
    }
