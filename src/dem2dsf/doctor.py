"""Environment and dependency checks for dem2dsf."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dem2dsf.scenery import validate_overlay_source
from dem2dsf.tools.config import load_tool_paths, ortho_root_from_paths
from dem2dsf.tools.ortho4xp import (
    TARGET_ORTHO4XP_VERSION,
    Ortho4XPNotFoundError,
    find_ortho4xp_script,
    ortho4xp_version,
    probe_python_runtime,
    read_config_values,
)

MIN_PYTHON = (3, 13)


@dataclass(frozen=True)
class CheckResult:
    """Result of a single doctor check."""

    name: str
    status: str
    detail: str


def _status(name: str, status: str, detail: str) -> CheckResult:
    """Helper to build a CheckResult."""
    return CheckResult(name=name, status=status, detail=detail)


def check_python_version() -> CheckResult:
    """Verify the running Python meets the minimum version."""
    if sys.version_info < MIN_PYTHON:
        return _status(
            "python",
            "error",
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required",
        )
    return _status("python", "ok", f"{sys.version_info.major}.{sys.version_info.minor}")


def check_python_deps() -> Iterable[CheckResult]:
    """Verify that key Python dependencies can be imported."""
    results = []
    try:
        import rasterio

        results.append(_status("rasterio", "ok", rasterio.__version__))
        results.append(_status("gdal", "ok", rasterio.__gdal_version__))
    except Exception as exc:  # pragma: no cover - import failure path
        results.append(_status("rasterio", "error", str(exc)))
    try:
        import pyproj

        results.append(_status("pyproj", "ok", pyproj.__version__))
    except Exception as exc:  # pragma: no cover - import failure path
        results.append(_status("pyproj", "error", str(exc)))
    return results


def check_command(name: str, command: list[str] | None) -> CheckResult:
    """Probe an external command for availability and basic responsiveness."""
    if not command:
        return _status(name, "warn", "not configured")
    binary = command[0]
    if Path(binary).exists() or shutil.which(binary):
        try:
            result = subprocess.run(
                command + ["--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return _status(name, "ok", "command responded to --help")
            return _status(name, "warn", f"non-zero exit: {result.returncode}")
        except OSError as exc:
            return _status(name, "error", str(exc))
    return _status(name, "error", "command not found")


def _runner_flag_value(runner: list[str] | None, flag: str) -> str | None:
    if not runner:
        return None
    for index, token in enumerate(runner):
        if token == flag and index + 1 < len(runner):
            return runner[index + 1]
        if token.startswith(f"{flag}="):
            return token.split("=", 1)[1]
    return None


def _resolve_ortho_root(
    ortho_runner: list[str] | None,
    tool_paths: dict[str, Path],
) -> Path | None:
    root_override = _runner_flag_value(ortho_runner, "--ortho-root")
    if root_override:
        return Path(root_override).expanduser()
    ortho_root = ortho_root_from_paths(tool_paths)
    if ortho_root:
        return ortho_root
    env_root = os.environ.get("ORTHO4XP_ROOT")
    if env_root:
        return Path(env_root).expanduser()
    return None


def check_ortho4xp_version(
    ortho_runner: list[str] | None,
    tool_paths: dict[str, Path],
) -> CheckResult:
    """Report the detected Ortho4XP script version if available."""
    script_path: Path | None = None
    script_override = _runner_flag_value(ortho_runner, "--ortho-script")
    if script_override:
        script_path = Path(script_override).expanduser()
        if not script_path.exists():
            return _status(
                "ortho4xp_version",
                "error",
                f"Ortho4XP script not found: {script_path}",
            )
    else:
        root_override = _runner_flag_value(ortho_runner, "--ortho-root")
        if root_override:
            try:
                script_path = find_ortho4xp_script(Path(root_override).expanduser())
            except Ortho4XPNotFoundError as exc:
                return _status("ortho4xp_version", "error", str(exc))
        else:
            script_path = tool_paths.get("ortho4xp")
            if not script_path:
                env_root = os.environ.get("ORTHO4XP_ROOT")
                if env_root:
                    try:
                        script_path = find_ortho4xp_script(Path(env_root).expanduser())
                    except Ortho4XPNotFoundError as exc:
                        return _status("ortho4xp_version", "error", str(exc))
    if not script_path:
        return _status("ortho4xp_version", "warn", "Ortho4XP not configured")
    if not script_path.exists():
        return _status(
            "ortho4xp_version",
            "error",
            f"Ortho4XP script not found: {script_path}",
        )
    version = ortho4xp_version(script_path)
    if not version:
        return _status(
            "ortho4xp_version",
            "warn",
            f"version not detected ({script_path.name})",
        )
    if not version.startswith("1.4"):
        return _status(
            "ortho4xp_version",
            "warn",
            f"Ortho4XP {version} detected; dem2dsf targets {TARGET_ORTHO4XP_VERSION}",
        )
    return _status("ortho4xp_version", "ok", version)


def check_ortho4xp_python(ortho_runner: list[str] | None) -> CheckResult:
    """Check the Python runtime used by the Ortho4XP runner."""
    if not ortho_runner:
        return _status("ortho4xp_python", "warn", "runner not configured")
    python_exe = _runner_flag_value(ortho_runner, "--python")
    resolved, version, error = probe_python_runtime(python_exe)
    if error:
        return _status("ortho4xp_python", "error", error)
    if not version:
        return _status("ortho4xp_python", "warn", "unable to detect python version")
    version_str = ".".join(str(part) for part in version)
    if version[0] < 3:
        return _status(
            "ortho4xp_python",
            "warn",
            f"Python {version_str} detected; Ortho4XP expects Python 3",
        )
    if python_exe and resolved:
        return _status("ortho4xp_python", "ok", f"{version_str} ({resolved})")
    return _status("ortho4xp_python", "ok", version_str)


def check_overlay_source(
    ortho_runner: list[str] | None,
    tool_paths: dict[str, Path],
) -> CheckResult:
    """Validate Ortho4XP overlay source configuration if present."""
    ortho_root = _resolve_ortho_root(ortho_runner, tool_paths)
    if not ortho_root:
        return _status(
            "overlay_source",
            "warn",
            "Ortho4XP root not configured",
        )
    config_path = ortho_root / "Ortho4XP.cfg"
    config = read_config_values(config_path)
    overlay_value = config.get("custom_overlay_src", "").strip()
    if not overlay_value:
        return _status(
            "overlay_source",
            "warn",
            f"custom_overlay_src not set in {config_path}",
        )
    overlay_path = Path(overlay_value).expanduser()
    if not overlay_path.is_absolute():
        overlay_path = (ortho_root / overlay_path).resolve()
    result = validate_overlay_source(overlay_path)
    status = result["status"]
    return _status("overlay_source", status, result["detail"])


def run_doctor(
    *,
    ortho_runner: list[str] | None,
    dsftool_path: list[str] | None,
    ddstool_path: list[str] | None = None,
) -> list[CheckResult]:
    """Run all environment checks and return the aggregated results."""
    tool_paths = load_tool_paths()
    results = [check_python_version(), *check_python_deps()]
    results.append(check_ortho4xp_version(ortho_runner, tool_paths))
    results.append(check_ortho4xp_python(ortho_runner))
    results.append(check_overlay_source(ortho_runner, tool_paths))
    results.append(check_command("ortho4xp_runner", ortho_runner))
    results.append(check_command("dsftool", dsftool_path))
    results.append(check_command("ddstool", ddstool_path))
    return results
