"""Command-line wrapper for running Ortho4XP builds."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
from pathlib import Path

from dem2dsf.logging_utils import LogOptions, configure_logging
from dem2dsf.tools.ortho4xp import (
    TARGET_ORTHO4XP_VERSION,
    Ortho4XPNotFoundError,
    build_command,
    copy_tile_outputs,
    default_scenery_root,
    find_ortho4xp_script,
    ortho4xp_version,
    parse_config_values,
    patch_config_values,
    probe_python_runtime,
    read_config_values,
    restore_config,
    stage_custom_dem,
    tile_scenery_dir,
)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the runner."""
    parser = argparse.ArgumentParser(description="Run Ortho4XP for a tile.")
    parser.add_argument("--tile", required=True, help="Tile name like +DD+DDD.")
    parser.add_argument("--dem", required=True, help="Path to the tile DEM.")
    parser.add_argument("--output", required=True, help="Output directory.")
    parser.add_argument(
        "--ortho-root",
        default=os.environ.get("ORTHO4XP_ROOT"),
        help="Path to the Ortho4XP root (or set ORTHO4XP_ROOT).",
    )
    parser.add_argument(
        "--ortho-script",
        help="Explicit Ortho4XP script path (defaults to auto-detect).",
    )
    parser.add_argument(
        "--scenery-root",
        help="Custom Scenery folder root (defaults to <ortho-root>/Custom Scenery).",
    )
    parser.add_argument(
        "--python",
        dest="python_exe",
        help="Python executable for Ortho4XP.",
    )
    parser.add_argument(
        "--ortho-arg",
        action="append",
        dest="ortho_args",
        help="Extra argument passed to Ortho4XP (repeatable).",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Pass --batch to Ortho4XP for headless runs.",
    )
    parser.add_argument(
        "--pass-output",
        action="store_true",
        help="Pass --output to Ortho4XP if your build script supports it.",
    )
    parser.add_argument(
        "--autoortho",
        action="store_true",
        help="Enable AutoOrtho-friendly settings (skip downloads).",
    )
    parser.add_argument(
        "--config-json",
        help="JSON map of Ortho4XP.cfg overrides (e.g. density presets).",
    )
    parser.add_argument(
        "--persist-config",
        action="store_true",
        help="Keep patched Ortho4XP.cfg changes after the run.",
    )
    parser.add_argument(
        "--skip-dem-stage",
        action="store_true",
        help="Skip copying the DEM into Ortho4XP Elevation_data.",
    )
    parser.add_argument(
        "--copy-textures",
        action="store_true",
        help="Copy textures into the output directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log the Ortho4XP command without running it.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (repeatable).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce log output to warnings and errors.",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Emit logs as JSON on stderr.",
    )
    parser.add_argument(
        "--log-file",
        help="Optional path for JSON log output.",
    )
    return parser.parse_args()


def _write_logs(
    output_dir: Path,
    tile: str,
    result: subprocess.CompletedProcess[str],
    *,
    attempt: int = 1,
) -> None:
    """Write stdout/stderr logs for a runner invocation."""
    log_dir = output_dir / "runner_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if attempt == 1 else f".attempt{attempt}"
    (log_dir / f"ortho4xp_{tile}{suffix}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (log_dir / f"ortho4xp_{tile}{suffix}.stderr.log").write_text(result.stderr, encoding="utf-8")
    events = parse_runner_events(result.stdout, result.stderr)
    (log_dir / f"ortho4xp_{tile}{suffix}.events.json").write_text(
        json.dumps(events, indent=2), encoding="utf-8"
    )


def _write_stage_metadata(output_dir: Path, tile: str, staged_path: Path) -> None:
    log_dir = output_dir / "runner_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {"staged_dem": str(staged_path)}
    (log_dir / f"ortho4xp_{tile}.staged.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


STEP_PATTERN = re.compile(r"\bStep\s+(\d+(?:\.\d+)?)\b", re.IGNORECASE)
TRIANGLE_FAILURE_PATTERN = re.compile(
    r"(triangle4xp|minimum allowable angle|tiny triangles|area criterion)",
    re.IGNORECASE,
)
LOGGER = logging.getLogger("dem2dsf.runner")
SENSITIVE_CONFIG_TOKENS = ("key", "token", "secret", "pass", "auth", "license")


def _event_from_line(line: str) -> dict[str, str] | None:
    stripped = line.strip()
    if not stripped:
        return None
    lowered = stripped.lower()
    match = STEP_PATTERN.search(stripped)
    if match:
        return {"event": "step", "step": match.group(1), "detail": stripped}
    if "start of the mesh algorithm" in lowered:
        return {"event": "triangle4xp_start", "detail": stripped}
    if "converted text dsf to binary dsf" in lowered:
        return {"event": "dsf_compiled", "detail": stripped}
    if "download" in lowered:
        return {"event": "download", "detail": stripped}
    if "overlay" in lowered and ("extract" in lowered or "overlay" in lowered):
        return {"event": "overlay", "detail": stripped}
    return None


def parse_runner_events(stdout: str, stderr: str) -> list[dict[str, str]]:
    """Parse Ortho4XP output into structured milestone events."""
    events: list[dict[str, str]] = []
    for stream, output in (("stdout", stdout), ("stderr", stderr)):
        for index, line in enumerate(output.splitlines(), start=1):
            event = _event_from_line(line)
            if not event:
                continue
            events.append(
                {
                    "stream": stream,
                    "line": index,
                    **event,
                }
            )
    return events


def _runner_env() -> dict[str, str]:
    env = dict(os.environ)
    source_root = Path(__file__).resolve().parents[3] / "src"
    if (source_root / "dem2dsf").exists():
        existing = env.get("PYTHONPATH", "")
        entries = [entry for entry in existing.split(os.pathsep) if entry]
        source_str = str(source_root)
        if source_str not in entries:
            entries.insert(0, source_str)
        env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in SENSITIVE_CONFIG_TOKENS)


def _config_diff(original: str | None, config_path: Path) -> dict[str, dict[str, str | None]]:
    original_values = parse_config_values(original or "")
    updated_values = read_config_values(config_path)
    diff: dict[str, dict[str, str | None]] = {}
    for key, new_value in updated_values.items():
        old_value = original_values.get(key)
        if old_value == new_value:
            continue
        if _is_sensitive_key(key):
            diff[key] = {
                "before": "<redacted>" if old_value is not None else None,
                "after": "<redacted>",
            }
        else:
            diff[key] = {"before": old_value, "after": new_value}
    return diff


def _write_config_diff(
    output_dir: Path,
    tile: str,
    diff: dict[str, dict[str, str | None]],
    *,
    attempt: int = 1,
) -> None:
    if not diff:
        return
    log_dir = output_dir / "runner_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if attempt == 1 else f".attempt{attempt}"
    payload = {"diff": diff}
    (log_dir / f"ortho4xp_{tile}{suffix}.config.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _run_with_config(
    *,
    config_path: Path,
    config_updates: dict[str, object],
    cmd: list[str],
    cwd: Path,
    persist_config: bool,
) -> tuple[subprocess.CompletedProcess[str], dict[str, dict[str, str | None]] | None]:
    original_config: str | None = None
    patched = False
    diff: dict[str, dict[str, str | None]] | None = None
    if config_updates:
        original_config = patch_config_values(config_path, config_updates)
        patched = True
        diff = _config_diff(original_config, config_path)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env=_runner_env(),
        )
        return result, diff
    finally:
        if patched and not persist_config:
            restore_config(config_path, original_config)


def _min_angle_from_config(config_path: Path, config_updates: dict[str, object]) -> float | None:
    if "min_angle" in config_updates:
        try:
            return float(config_updates["min_angle"])
        except (TypeError, ValueError):
            return None
    config = read_config_values(config_path)
    if "min_angle" in config:
        try:
            return float(config["min_angle"])
        except (TypeError, ValueError):
            return None
    return None


def _retry_min_angles(base: float | None) -> list[float]:
    ladder = [5.0, 0.0]
    if base is None:
        return ladder
    return [value for value in ladder if value < base]


def _needs_triangulation_retry(stdout: str, stderr: str) -> bool:
    output = f"{stdout}\n{stderr}"
    return bool(TRIANGLE_FAILURE_PATTERN.search(output))


def main() -> int:
    """Run Ortho4XP for a tile and copy outputs."""
    args = _parse_args()
    output_dir = Path(args.output)
    log_file = (
        Path(args.log_file)
        if args.log_file
        else output_dir / "runner_logs" / f"ortho4xp_{args.tile}.run.log"
    )
    configure_logging(
        LogOptions(
            verbose=args.verbose or 0,
            quiet=args.quiet,
            log_file=log_file,
            json_console=args.log_json,
        )
    )
    log_extra = {"tile": args.tile}
    if not args.ortho_root:
        LOGGER.error(
            "Ortho4XP root not provided. Use --ortho-root or ORTHO4XP_ROOT.",
            extra=log_extra,
        )
        return 2

    ortho_root = Path(args.ortho_root)
    dem_path = Path(args.dem)
    if not ortho_root.exists():
        LOGGER.error("Ortho4XP root not found: %s", ortho_root, extra=log_extra)
        return 2
    if not dem_path.exists():
        LOGGER.error("DEM path not found: %s", dem_path, extra=log_extra)
        return 2
    if args.scenery_root:
        scenery_root_path = Path(args.scenery_root)
        if not scenery_root_path.exists():
            LOGGER.error(
                "Custom Scenery root not found: %s",
                scenery_root_path,
                extra=log_extra,
            )
            return 2
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        LOGGER.error(
            "Unable to create output directory %s: %s",
            output_dir,
            exc,
            extra=log_extra,
        )
        return 2

    try:
        script_path = (
            Path(args.ortho_script) if args.ortho_script else find_ortho4xp_script(ortho_root)
        )
    except Ortho4XPNotFoundError as exc:
        LOGGER.error("%s", exc, extra=log_extra)
        return 2
    if args.ortho_script and not script_path.exists():
        LOGGER.error("Ortho4XP script not found: %s", script_path, extra=log_extra)
        return 2

    resolved_python, version, error = probe_python_runtime(args.python_exe)
    if error:
        LOGGER.error("Ortho4XP python check failed: %s", error, extra=log_extra)
        return 2
    if version and version[0] < 3:
        version_str = ".".join(str(part) for part in version)
        LOGGER.warning(
            "Python %s detected; Ortho4XP expects Python 3.",
            version_str,
            extra=log_extra,
        )

    ortho_version = ortho4xp_version(script_path)
    if not ortho_version:
        LOGGER.warning(
            "Ortho4XP version not detected from %s.",
            script_path.name,
            extra=log_extra,
        )
    elif not ortho_version.startswith("1.4"):
        LOGGER.warning(
            "Ortho4XP %s detected; dem2dsf targets %s.",
            ortho_version,
            TARGET_ORTHO4XP_VERSION,
            extra=log_extra,
        )

    config_updates: dict[str, object] = {}
    if args.config_json:
        try:
            parsed = json.loads(args.config_json)
        except json.JSONDecodeError as exc:
            LOGGER.error("Invalid --config-json payload: %s", exc, extra=log_extra)
            return 2
        if not isinstance(parsed, dict):
            LOGGER.error("--config-json must decode to an object.", extra=log_extra)
            return 2
        config_updates.update(parsed)
    if args.autoortho:
        config_updates["skip_downloads"] = True

    if not args.skip_dem_stage:
        staged_path = stage_custom_dem(ortho_root, args.tile, dem_path)
        _write_stage_metadata(output_dir, args.tile, staged_path)

    extra_args = list(args.ortho_args or [])
    if args.batch:
        extra_args.append("--batch")

    cmd = build_command(
        script_path,
        args.tile,
        output_dir,
        python_exe=resolved_python if args.python_exe else None,
        extra_args=extra_args,
        include_output=args.pass_output,
    )

    if args.dry_run:
        LOGGER.info("Dry run command: %s", " ".join(cmd), extra=log_extra)
        return 0

    config_path = ortho_root / "Ortho4XP.cfg"
    attempt = 1
    base_min_angle = _min_angle_from_config(config_path, config_updates)
    result, config_diff = _run_with_config(
        config_path=config_path,
        config_updates=config_updates,
        cmd=cmd,
        cwd=ortho_root,
        persist_config=args.persist_config,
    )
    _write_logs(output_dir, args.tile, result, attempt=attempt)
    if config_diff:
        _write_config_diff(output_dir, args.tile, config_diff, attempt=attempt)
    if result.returncode != 0 and _needs_triangulation_retry(result.stdout, result.stderr):
        for min_angle in _retry_min_angles(base_min_angle):
            attempt += 1
            LOGGER.warning(
                "Retrying Triangle4XP with min_angle=%s",
                min_angle,
                extra={**log_extra, "attempt": attempt, "min_angle": min_angle},
            )
            retry_updates = {**config_updates, "min_angle": min_angle}
            result, config_diff = _run_with_config(
                config_path=config_path,
                config_updates=retry_updates,
                cmd=cmd,
                cwd=ortho_root,
                persist_config=args.persist_config,
            )
            _write_logs(output_dir, args.tile, result, attempt=attempt)
            if config_diff:
                _write_config_diff(output_dir, args.tile, config_diff, attempt=attempt)
            if result.returncode == 0:
                break
    if result.returncode != 0:
        LOGGER.error(
            "Ortho4XP runner failed; see runner_logs for details.",
            extra=log_extra,
        )
        return result.returncode

    scenery_root = (
        Path(args.scenery_root) if args.scenery_root else default_scenery_root(ortho_root)
    )
    tile_dir = tile_scenery_dir(scenery_root, args.tile)
    if not tile_dir.exists():
        LOGGER.error("Expected tile output not found: %s", tile_dir, extra=log_extra)
        return 3

    copy_tile_outputs(tile_dir, output_dir, include_textures=args.copy_textures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
