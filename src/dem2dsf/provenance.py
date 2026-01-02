"""Provenance and determinism helpers for build metadata."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from dem2dsf.dem.models import CoverageMetrics
from dem2dsf.publish import find_sevenzip
from dem2dsf.tools.config import load_tool_paths
from dem2dsf.tools.dsftool import dsftool_version
from dem2dsf.tools.ortho4xp import (
    Ortho4XPNotFoundError,
    find_ortho4xp_script,
    ortho4xp_version,
    probe_python_runtime,
)

PROVENANCE_LEVELS = ("basic", "strict")
ENV_PINNED_VERSIONS = "DEM2DSF_PINNED_VERSIONS"
_VERSION_PATTERN = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def _normalize_command(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_fingerprint(path: Path, *, strict: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": str(path)}
    try:
        stat = path.stat()
    except OSError as exc:
        payload["error"] = str(exc)
        return payload
    payload["size"] = stat.st_size
    payload["mtime_ns"] = stat.st_mtime_ns
    if strict:
        try:
            payload["sha256"] = _sha256(path)
        except OSError as exc:
            payload["sha256_error"] = str(exc)
    return payload


def _resolve_command_path(command: Sequence[str] | None) -> str | None:
    if not command:
        return None
    for token in reversed(command):
        candidate = Path(token)
        if candidate.exists():
            return str(candidate)
    resolved = shutil.which(command[0])
    return resolved


def _command_info(command: Sequence[str] | None) -> dict[str, Any] | None:
    if not command:
        return None
    payload: dict[str, Any] = {"command": list(command)}
    resolved = _resolve_command_path(command)
    if resolved:
        payload["resolved_path"] = resolved
    return payload


def _runner_flag_value(runner: Sequence[str] | None, flag: str) -> str | None:
    if not runner:
        return None
    for index, token in enumerate(runner):
        if token == flag and index + 1 < len(runner):
            return runner[index + 1]
        if token.startswith(f"{flag}="):
            return token.split("=", 1)[1]
    return None


def _resolve_ortho4xp_script(runner: Sequence[str] | None) -> Path | None:
    script_override = _runner_flag_value(runner, "--ortho-script")
    if script_override:
        candidate = Path(script_override).expanduser()
        return candidate if candidate.exists() else None
    root_override = _runner_flag_value(runner, "--ortho-root")
    if root_override:
        try:
            return find_ortho4xp_script(Path(root_override).expanduser())
        except Ortho4XPNotFoundError:
            return None
    tool_paths = load_tool_paths()
    tool_script = tool_paths.get("ortho4xp")
    if tool_script and tool_script.exists():
        return tool_script
    env_root = os.environ.get("ORTHO4XP_ROOT")
    if env_root:
        try:
            return find_ortho4xp_script(Path(env_root).expanduser())
        except Ortho4XPNotFoundError:
            return None
    return None


def _git_commit_for_path(path: Path) -> str | None:
    for candidate in [path, *path.parents]:
        git_dir = candidate / ".git"
        if git_dir.is_dir():
            head = git_dir / "HEAD"
            try:
                head_value = head.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            if head_value.startswith("ref: "):
                ref = head_value.split("ref: ", 1)[1].strip()
                ref_path = git_dir / ref
                try:
                    return ref_path.read_text(encoding="utf-8").strip()
                except OSError:
                    return None
            return head_value or None
    return None


def _sevenzip_version(sevenzip_path: Path) -> str | None:
    try:
        result = subprocess.run(
            [str(sevenzip_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    output = (result.stdout or result.stderr or "").strip()
    match = _VERSION_PATTERN.search(output)
    if not match:
        return None
    parts = [match.group(1), match.group(2), match.group(3)]
    return ".".join(part for part in parts if part)


def _dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    try:
        import rasterio

        versions["rasterio"] = rasterio.__version__
        versions["gdal"] = rasterio.__gdal_version__
    except Exception:
        pass
    try:
        import pyproj

        versions["pyproj"] = pyproj.__version__
    except Exception:
        pass
    try:
        import numpy

        versions["numpy"] = numpy.__version__
    except Exception:
        pass
    return versions


def _parse_version(value: str) -> tuple[int, ...] | None:
    digits = re.findall(r"\d+", value)
    if not digits:
        return None
    return tuple(int(item) for item in digits[:3])


def _version_matches(pinned: str, actual: str) -> bool | None:
    if pinned.endswith("+"):
        minimum = _parse_version(pinned[:-1])
        observed = _parse_version(actual)
        if not minimum or not observed:
            return None
        return observed >= minimum
    pinned_version = _parse_version(pinned)
    actual_version = _parse_version(actual)
    if pinned_version and actual_version:
        return actual_version[: len(pinned_version)] == pinned_version
    return actual == pinned


def _coverage_summary(metrics: Mapping[str, CoverageMetrics] | None) -> dict[str, Any] | None:
    if not metrics:
        return None
    coverage_before = [item.coverage_before for item in metrics.values()]
    coverage_after = [item.coverage_after for item in metrics.values()]
    normalize_seconds = [item.normalize_seconds for item in metrics.values()]
    return {
        "tile_count": len(metrics),
        "coverage_before_min": min(coverage_before),
        "coverage_before_avg": sum(coverage_before) / len(coverage_before),
        "coverage_after_min": min(coverage_after),
        "coverage_after_avg": sum(coverage_after) / len(coverage_after),
        "normalize_seconds_total": sum(normalize_seconds),
    }


def load_pinned_versions(path: Path | None = None) -> tuple[dict[str, str], str | None]:
    candidate: Path | None = path
    if candidate is None:
        env_path = os.environ.get(ENV_PINNED_VERSIONS)
        if env_path:
            candidate = Path(env_path)
    if candidate is not None:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}, str(candidate)
        if not isinstance(payload, dict):
            return {}, str(candidate)
        return {str(key): str(value) for key, value in payload.items()}, str(candidate)
    try:
        resource = resources.files("dem2dsf").joinpath("resources", "pinned_versions.json")
        with resource.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, ModuleNotFoundError, OSError, json.JSONDecodeError):
        return {}, None
    if not isinstance(payload, dict):
        return {}, None
    return (
        {str(key): str(value) for key, value in payload.items()},
        "package:dem2dsf/resources/pinned_versions.json",
    )


def build_provenance(
    *,
    options: Mapping[str, Any],
    dem_paths: Iterable[Path],
    coverage_metrics: Mapping[str, CoverageMetrics] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    level = str(options.get("provenance_level", "basic"))
    if level not in PROVENANCE_LEVELS:
        level = "basic"
    strict = level == "strict"

    inputs: dict[str, Any] = {
        "dems": [_file_fingerprint(path, strict=strict) for path in dem_paths],
    }
    fallback = [Path(path) for path in options.get("fallback_dem_paths") or []]
    if fallback:
        inputs["fallback_dems"] = [_file_fingerprint(path, strict=strict) for path in fallback]
    dem_stack_path = options.get("dem_stack_path")
    if dem_stack_path:
        inputs["dem_stack_path"] = str(dem_stack_path)

    runner_cmd = _normalize_command(options.get("runner"))
    dsftool_cmd = _normalize_command(options.get("dsftool"))

    tools: dict[str, Any] = {}
    runner_info = _command_info(runner_cmd)
    if runner_info:
        tools["runner"] = runner_info
    dsftool_info = _command_info(dsftool_cmd)
    if dsftool_info and dsftool_cmd:
        dsftool_info["executable"] = dsftool_cmd[-1]
        tools["dsftool"] = dsftool_info

    ortho_script = _resolve_ortho4xp_script(runner_cmd)
    if ortho_script:
        ortho_info: dict[str, Any] = {"script_path": str(ortho_script)}
        ortho_version = ortho4xp_version(ortho_script)
        if ortho_version:
            ortho_info["version"] = ortho_version
        if strict:
            ortho_info["git_commit"] = _git_commit_for_path(ortho_script.parent)
            python_exe = _runner_flag_value(runner_cmd, "--python")
            resolved, version, error = probe_python_runtime(python_exe)
            if resolved:
                ortho_info["python_executable"] = resolved
            if version:
                ortho_info["python_version"] = ".".join(str(part) for part in version)
            if error:
                ortho_info["python_error"] = error
        tools["ortho4xp"] = ortho_info

    sevenzip_path = find_sevenzip(None)
    if sevenzip_path:
        sevenzip_info: dict[str, Any] = {"resolved_path": str(sevenzip_path)}
        if strict:
            sevenzip_info["version"] = _sevenzip_version(sevenzip_path)
        tools["sevenzip"] = sevenzip_info

    if strict and dsftool_cmd:
        try:
            existing_info = tools.get("dsftool")
            if isinstance(existing_info, dict):
                strict_dsftool_info: dict[str, Any] = dict(existing_info)
            else:
                strict_dsftool_info = {"command": list(dsftool_cmd)}
            dsftool_version_value = dsftool_version(dsftool_cmd)
            if dsftool_version_value:
                strict_dsftool_info["version"] = ".".join(
                    str(part) for part in dsftool_version_value
                )
            tools["dsftool"] = strict_dsftool_info
        except Exception:
            pass

    deps = _dependency_versions()
    environment = {
        "python": {
            "path": sys.executable,
            "version": ".".join(str(part) for part in sys.version_info[:3]),
        },
        "deps": deps,
    }

    coverage_summary = _coverage_summary(coverage_metrics)
    coverage = {
        "metrics_enabled": bool(
            options.get("coverage_metrics", True) or options.get("coverage_min") is not None
        ),
        "min_coverage": options.get("coverage_min"),
        "hard_fail": bool(options.get("coverage_hard_fail", False)),
    }
    if coverage_summary:
        coverage["summary"] = coverage_summary

    provenance: dict[str, Any] = {
        "level": level,
        "stable_metadata": bool(options.get("stable_metadata", False)),
        "inputs": inputs,
        "tools": tools,
        "environment": environment,
        "assumptions": {"vertical_units": options.get("vertical_units") or "meters"},
        "coverage": coverage,
    }

    pinned_path = options.get("pinned_versions_path")
    pinned_versions, pinned_source = load_pinned_versions(
        Path(pinned_path) if pinned_path else None
    )
    warnings: list[str] = []
    if pinned_versions:
        provenance["pinned_versions"] = pinned_versions
        if pinned_source:
            provenance["pinned_versions_source"] = pinned_source
        observed_versions: dict[str, str] = {}
        python_version = environment["python"]["version"]
        if python_version:
            observed_versions["python"] = python_version
        gdal_version = deps.get("gdal")
        if gdal_version:
            observed_versions["gdal"] = gdal_version
        ortho_version = tools.get("ortho4xp", {}).get("version")
        if ortho_version:
            observed_versions["ortho4xp"] = ortho_version
        dsftool_version_value = tools.get("dsftool", {}).get("version")
        if dsftool_version_value:
            observed_versions["dsftool"] = dsftool_version_value
        sevenzip_version = tools.get("sevenzip", {}).get("version")
        if sevenzip_version:
            observed_versions["sevenzip"] = sevenzip_version

        mismatches: list[dict[str, str]] = []
        missing: list[dict[str, str]] = []
        for tool, pinned in pinned_versions.items():
            observed = observed_versions.get(tool)
            if not observed:
                missing.append({"tool": tool, "pinned": pinned})
                continue
            matches = _version_matches(pinned, observed)
            if matches is False:
                mismatches.append({"tool": tool, "pinned": pinned, "observed": observed})
        provenance["version_drift"] = {
            "observed": observed_versions,
            "mismatches": mismatches,
            "missing": missing,
        }
        if strict:
            for mismatch in mismatches:
                warning = (
                    "Pinned version mismatch: "
                    f"{mismatch['tool']} expected {mismatch['pinned']}, "
                    f"found {mismatch['observed']}"
                )
                warnings.append(warning)

    return provenance, warnings
