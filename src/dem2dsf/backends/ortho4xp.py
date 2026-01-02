"""Backend adapter that shells out to an Ortho4XP runner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from dem2dsf import contracts
from dem2dsf.backends.base import BackendSpec, BuildRequest, BuildResult
from dem2dsf.density import ortho4xp_config_for_preset
from dem2dsf.reporting import build_plan, build_report
from dem2dsf.subprocess_utils import run_command
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path


class Ortho4XPBackend:
    """Execute Ortho4XP builds and format build reports."""

    def spec(self) -> BackendSpec:
        """Return backend capability metadata."""
        return BackendSpec(
            name="ortho4xp",
            version="1.40",
            artifact_schema_version=contracts.SCHEMA_VERSION,
            tile_dem_crs="EPSG:4326",
            supports_xp12_rasters=True,
            supports_autoortho=True,
        )

    def build(self, request: BuildRequest) -> BuildResult:
        """Run the configured Ortho4XP runner for each tile."""
        options = dict(request.options)
        warnings: list[str] = []
        errors: list[str] = []
        density = options.get("density", "medium")
        try:
            options["backend_config"] = ortho4xp_config_for_preset(density)
        except ValueError as exc:
            warnings.append(str(exc))
            options["backend_config"] = {}

        plan = build_plan(
            backend=self.spec(),
            tiles=request.tiles,
            dem_paths=[str(path) for path in request.dem_paths],
            options=options,
            aoi=options.get("aoi"),
        )

        runner = _normalize_runner(options.get("runner"))
        if not runner:
            errors.append(
                "Ortho4XP runner not configured. Set --runner or configure tools/tool_paths.json."
            )
            tile_statuses = [
                {
                    "tile": tile,
                    "status": "skipped",
                    "messages": ["runner not configured"],
                }
                for tile in request.tiles
            ]
            report = build_report(
                backend=self.spec(),
                tile_statuses=tile_statuses,
                artifacts={"scenery_dir": str(request.output_dir)},
                warnings=warnings,
                errors=errors,
            )
            return BuildResult(build_plan=plan, build_report=report)
        runner_error = _validate_runner(runner)
        if runner_error:
            errors.append(runner_error)
            tile_statuses = [
                {
                    "tile": tile,
                    "status": "skipped",
                    "messages": [runner_error],
                }
                for tile in request.tiles
            ]
            report = build_report(
                backend=self.spec(),
                tile_statuses=tile_statuses,
                artifacts={"scenery_dir": str(request.output_dir)},
                warnings=warnings,
                errors=errors,
            )
            return BuildResult(build_plan=plan, build_report=report)

        dem_path = request.dem_paths[0] if request.dem_paths else None
        if dem_path is None:
            errors.append("No DEM paths provided.")

        tile_dem_paths = options.get("tile_dem_paths") or {}
        if len(request.dem_paths) > 1 and not tile_dem_paths:
            warnings.append("Multiple DEMs provided; using the first for all tiles.")
        normalization_errors = options.get("normalization_errors") or {}
        runner_timeout = options.get("runner_timeout")
        runner_retries = int(options.get("runner_retries", 0) or 0)
        runner_stream_logs = bool(options.get("runner_stream_logs", False))

        tile_statuses = []
        dsf_paths = []
        extra_args = []
        if options.get("autoortho") and _runner_supports_autoortho(runner):
            extra_args.append("--autoortho")
        backend_config = options.get("backend_config") or {}
        if backend_config and _runner_supports_autoortho(runner):
            extra_args.extend(
                [
                    "--config-json",
                    json.dumps(backend_config, separators=(",", ":")),
                ]
            )
        for tile in request.tiles:
            messages = []
            status = "ok"
            if tile in normalization_errors:
                tile_statuses.append(
                    {
                        "tile": tile,
                        "status": "error",
                        "messages": [f"Normalization failed: {normalization_errors[tile]}"],
                    }
                )
                errors.append(f"{tile}: normalization failed")
                continue
            tile_dem = Path(tile_dem_paths.get(tile, dem_path)) if dem_path else None
            if tile_dem is None:
                tile_statuses.append({"tile": tile, "status": "error", "messages": ["missing DEM"]})
                continue
            if not tile_dem.exists():
                tile_statuses.append(
                    {
                        "tile": tile,
                        "status": "error",
                        "messages": [f"DEM not found: {tile_dem}"],
                    }
                )
                continue
            result = _run_runner(
                runner,
                tile,
                tile_dem,
                request.output_dir,
                extra_args=extra_args,
                timeout=runner_timeout,
                retries=runner_retries,
                stream_logs=runner_stream_logs,
            )
            if result.returncode != 0:
                status = "error"
                stderr = result.stderr.strip() or "runner failed"
                if result.returncode == 124 and runner_timeout:
                    stderr = f"Runner timed out after {runner_timeout} seconds."
                messages.append(stderr)
            dsf_path = _expected_dsf_path(request.output_dir, tile)
            if dsf_path.exists():
                dsf_paths.append(str(dsf_path))
            else:
                status = "warning" if status == "ok" else status
                messages.append("DSF output not found")
            tile_entry = {"tile": tile, "status": status, "messages": messages}
            metrics = tile_entry.setdefault("metrics", {})
            metrics["runner_command"] = list(result.args)
            staged_dem = _read_stage_metadata(request.output_dir, tile)
            if staged_dem:
                metrics["staged_dem"] = staged_dem
            config_diff = _read_config_diff(request.output_dir, tile)
            if config_diff:
                metrics["ortho4xp_config_diff"] = config_diff.get("diff", config_diff)
            tile_statuses.append(tile_entry)

        report = build_report(
            backend=self.spec(),
            tile_statuses=tile_statuses,
            artifacts={"scenery_dir": str(request.output_dir), "dsf_paths": dsf_paths},
            warnings=warnings,
            errors=errors,
        )
        return BuildResult(build_plan=plan, build_report=report)


def _normalize_runner(value: object) -> list[str] | None:
    """Normalize runner configuration into a command list."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    raise TypeError("Runner must be a string or list of strings.")


def _runner_log_paths(output_dir: Path, tile: str, attempt: int) -> tuple[Path, Path]:
    log_dir = output_dir / "runner_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if attempt <= 1 else f".attempt{attempt}"
    stdout_path = log_dir / f"backend_{tile}{suffix}.stdout.log"
    stderr_path = log_dir / f"backend_{tile}{suffix}.stderr.log"
    return stdout_path, stderr_path


def _read_stage_metadata(output_dir: Path, tile: str) -> str | None:
    path = output_dir / "runner_logs" / f"ortho4xp_{tile}.staged.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    staged = payload.get("staged_dem")
    if isinstance(staged, str) and staged:
        return staged
    return None


def _read_config_diff(output_dir: Path, tile: str) -> dict[str, Any] | None:
    log_dir = output_dir / "runner_logs"
    if not log_dir.exists():
        return None
    candidates: list[tuple[int, Path]] = []
    base_path = log_dir / f"ortho4xp_{tile}.config.json"
    if base_path.exists():
        candidates.append((1, base_path))
    for path in log_dir.glob(f"ortho4xp_{tile}.attempt*.config.json"):
        name = path.name
        attempt = 0
        if ".attempt" in name:
            suffix = name.split(".attempt", 1)[1]
            attempt_str = suffix.split(".config", 1)[0]
            if attempt_str.isdigit():
                attempt = int(attempt_str)
        candidates.append((attempt, path))
    if not candidates:
        return None
    _attempt, path = max(candidates, key=lambda item: item[0])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _run_runner(
    runner: list[str],
    tile: str,
    dem_path: Path,
    output_dir: Path,
    *,
    extra_args: list[str] | None = None,
    timeout: float | None = None,
    retries: int = 0,
    stream_logs: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Invoke the external runner process for a tile."""
    cmd = [
        *runner,
        "--tile",
        tile,
        "--dem",
        str(dem_path),
        "--output",
        str(output_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)
    attempts = max(0, int(retries))
    last_result = subprocess.CompletedProcess(cmd, 1, "", "")
    for attempt in range(1, attempts + 2):
        stdout_path = None
        stderr_path = None
        if stream_logs:
            stdout_path, stderr_path = _runner_log_paths(output_dir, tile, attempt)
        try:
            result = run_command(
                cmd,
                cwd=None,
                timeout=timeout,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            last_result = subprocess.CompletedProcess(
                cmd, result.returncode, result.stdout, result.stderr
            )
        except OSError as exc:
            return subprocess.CompletedProcess(cmd, 1, "", str(exc))
        if last_result.returncode == 0:
            return last_result
    return last_result


def _expected_dsf_path(output_dir: Path, tile: str) -> Path:
    """Return the expected DSF output path for a tile."""
    return xplane_dsf_path(output_dir, tile)


def _runner_supports_autoortho(runner: list[str]) -> bool:
    """Check if the runner command looks like the bundled Ortho4XP wrapper."""
    return any(
        token in part
        for part in runner
        for token in ("ortho4xp_runner.py", "dem2dsf-ortho4xp", "dem2dsf.runners.ortho4xp")
    )


def _runner_flag_present(runner: list[str], flag: str) -> bool:
    for token in runner:
        if token == flag or token.startswith(f"{flag}="):
            return True
    return False


def _validate_runner(runner: list[str]) -> str | None:
    binary = runner[0] if runner else ""
    if not binary:
        return "Runner command is empty."
    if not Path(binary).exists() and not shutil.which(binary):
        return f"Runner executable not found: {binary}"
    if _runner_supports_autoortho(runner):
        has_root = _runner_flag_present(runner, "--ortho-root")
        if not has_root and not os.environ.get("ORTHO4XP_ROOT"):
            return "Ortho4XP root not configured (use --ortho-root or ORTHO4XP_ROOT)."
    return None
