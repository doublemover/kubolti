"""Interactive wizard for build configuration."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, Mapping

from dem2dsf.build import run_build
from dem2dsf.density import DENSITY_PRESETS

FILL_CHOICES = ("none", "constant", "interpolate", "fallback")
RESAMPLING_CHOICES = ("nearest", "bilinear", "cubic", "average")
MOSAIC_CHOICES = ("full", "per-tile", "vrt")
COMPRESSION_CHOICES = ("none", "lzw", "deflate")


def _prompt_list(prompt: str) -> list[str]:
    """Prompt for a comma-separated list."""
    value = input(prompt).strip()
    return [item.strip() for item in value.split(",") if item.strip()]


def _prompt_choice(prompt: str, choices: tuple[str, ...], default: str) -> str:
    """Prompt for a choice value with validation."""
    choices_text = "/".join(choices)
    while True:
        value = input(f"{prompt} [{choices_text}] (default {default}): ").strip()
        if not value:
            return default
        for choice in choices:
            if choice.lower() == value.lower():
                return choice
        print(f"Choose one of: {', '.join(choices)}")


def _prompt_optional_float(prompt: str, default: float | None) -> float | None:
    """Prompt for an optional float value."""
    label = f"{prompt} (default {default}): " if default is not None else f"{prompt}: "
    while True:
        value = input(label).strip()
        if not value:
            return default
        try:
            return float(value)
        except ValueError:
            print("Enter a numeric value or leave blank.")


def _prompt_optional_int(prompt: str, default: int | None) -> int | None:
    """Prompt for an optional integer value."""
    label = f"{prompt} (default {default}): " if default is not None else f"{prompt}: "
    while True:
        value = input(label).strip()
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            print("Enter a whole number or leave blank.")


def _prompt_bool(prompt: str, default: bool) -> bool:
    """Prompt for a yes/no value."""
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes", "true", "1"}:
            return True
        if value in {"n", "no", "false", "0"}:
            return False
        print("Enter y/n.")


def _prompt_optional_str(prompt: str, default: str | None) -> str | None:
    """Prompt for an optional string value."""
    label = f"{prompt} (default {default}): " if default else f"{prompt}: "
    value = input(label).strip()
    return value or default


def _format_command(value: object) -> str | None:
    """Format a command for display in a prompt."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    if isinstance(value, str):
        return value
    return str(value)


def _prompt_command(prompt: str, default: object) -> list[str] | None:
    """Prompt for a command and parse it into a list."""
    value = _prompt_optional_str(prompt, _format_command(default))
    if not value:
        return None
    return shlex.split(value, posix=os.name != "nt")


def run_wizard(
    *,
    dem_paths: list[str] | None,
    tiles: list[str] | None,
    output_dir: Path,
    options: Mapping[str, Any],
    defaults: bool,
) -> None:
    """Run the interactive wizard and execute a build."""
    stack_path = options.get("dem_stack_path")
    if defaults:
        if not tiles:
            raise ValueError("Defaults mode requires --tile values.")
        if not dem_paths and not stack_path:
            raise ValueError("Defaults mode requires --dem or --dem-stack values.")
        run_build(
            dem_paths=[Path(path) for path in (dem_paths or [])],
            tiles=tiles,
            backend_name="ortho4xp",
            output_dir=output_dir,
            options=options,
        )
        return

    if not dem_paths and not stack_path:
        stack_input = _prompt_optional_str(
            "DEM stack JSON path (leave blank for DEM list)",
            None,
        )
        if stack_input:
            stack_path = stack_input
            options = {**options, "dem_stack_path": stack_path}
        else:
            dem_paths = _prompt_list("Enter DEM path(s), comma-separated: ")
    if not tiles:
        tiles = _prompt_list("Enter tile name(s), comma-separated: ")
    if not tiles:
        raise ValueError("Wizard requires tiles.")
    if not dem_paths and not stack_path:
        raise ValueError("Wizard requires DEMs or a DEM stack.")

    output_input = _prompt_optional_str("Output directory", str(output_dir))
    if output_input:
        output_dir = Path(output_input)
    runner_cmd = _prompt_command(
        "Runner command override (blank for defaults)",
        options.get("runner"),
    )
    dsftool_cmd = _prompt_command(
        "DSFTool command override (blank for defaults)",
        options.get("dsftool"),
    )
    runner_timeout = _prompt_optional_float(
        "Runner timeout seconds (blank for none)",
        options.get("runner_timeout"),
    )
    runner_retries = _prompt_optional_int(
        "Runner retries",
        int(options.get("runner_retries", 0) or 0),
    )
    runner_stream_logs = _prompt_bool(
        "Stream runner logs",
        bool(options.get("runner_stream_logs", False)),
    )
    persist_config = _prompt_bool(
        "Persist Ortho4XP.cfg changes",
        bool(options.get("persist_config", False)),
    )
    dsftool_timeout = _prompt_optional_float(
        "DSFTool timeout seconds (blank for none)",
        options.get("dsftool_timeout"),
    )
    dsftool_retries = _prompt_optional_int(
        "DSFTool retries",
        int(options.get("dsftool_retries", 0) or 0),
    )

    quality = _prompt_choice(
        "Raster quality",
        ("compat", "xp12-enhanced"),
        options.get("quality", "compat"),
    )
    density = _prompt_choice(
        "Density preset",
        tuple(DENSITY_PRESETS.keys()),
        options.get("density", "medium"),
    )
    autoortho = _prompt_bool(
        "Enable AutoOrtho mode (skip downloads)",
        bool(options.get("autoortho", False)),
    )
    skip_normalize = _prompt_bool(
        "Skip DEM normalization",
        not bool(options.get("normalize", True)),
    )
    target_crs = options.get("target_crs") or "EPSG:4326"
    resampling = options.get("resampling", "bilinear")
    target_resolution = options.get("target_resolution")
    dst_nodata = options.get("dst_nodata")
    fill_strategy = options.get("fill_strategy", "none")
    fill_value = float(options.get("fill_value", 0.0) or 0.0)
    fallback_dem_paths = list(options.get("fallback_dem_paths") or [])
    mosaic_strategy = options.get("mosaic_strategy", "full")
    normalized_compression = options.get("normalized_compression") or "none"
    cache_sha256 = bool(options.get("cache_sha256", False))
    if not skip_normalize:
        target_crs = _prompt_optional_str("Target CRS", target_crs)
        resampling = _prompt_choice(
            "Resampling method",
            RESAMPLING_CHOICES,
            resampling,
        )
        target_resolution = _prompt_optional_float(
            "Target resolution in meters (blank preserves source)",
            target_resolution,
        )
        dst_nodata = _prompt_optional_float(
            "Destination nodata (blank preserves source)",
            dst_nodata,
        )
        fill_strategy = _prompt_choice(
            "Fill strategy",
            FILL_CHOICES,
            fill_strategy,
        )
        if fill_strategy == "constant":
            fill_value = float(_prompt_optional_float("Fill value", fill_value) or fill_value)
        elif fill_strategy == "fallback":
            fallback_dem_paths = _prompt_list("Fallback DEM path(s), comma-separated: ")
            if not fallback_dem_paths:
                raise ValueError("Fallback strategy requires fallback DEM paths.")
        mosaic_strategy = _prompt_choice(
            "Mosaic strategy",
            MOSAIC_CHOICES,
            mosaic_strategy,
        )
        normalized_compression = _prompt_choice(
            "Normalized tile compression",
            COMPRESSION_CHOICES,
            normalized_compression,
        )
        cache_sha256 = _prompt_bool(
            "Validate normalization cache with SHA-256",
            cache_sha256,
        )

    tile_jobs = _prompt_optional_int(
        "Tile workers (0=auto, 1=serial)",
        options.get("tile_jobs", 1),
    )
    continue_on_error = _prompt_bool(
        "Continue on error",
        bool(options.get("continue_on_error", False)),
    )
    coverage_metrics = _prompt_bool(
        "Collect coverage metrics",
        bool(options.get("coverage_metrics", True)),
    )
    coverage_min = _prompt_optional_float(
        "Minimum coverage ratio (0-1, blank for none)",
        options.get("coverage_min"),
    )
    coverage_hard_fail = False
    if coverage_min is not None:
        coverage_hard_fail = _prompt_bool(
            "Fail tiles below minimum coverage",
            bool(options.get("coverage_hard_fail", False)),
        )
    triangle_warn = _prompt_optional_int(
        "Triangle warn threshold (blank = preset)", options.get("triangle_warn")
    )
    triangle_max = _prompt_optional_int(
        "Triangle max threshold (blank = preset)", options.get("triangle_max")
    )
    allow_triangle_overage = _prompt_bool(
        "Allow triangle overage",
        bool(options.get("allow_triangle_overage", False)),
    )
    global_scenery = _prompt_optional_str("Global Scenery path", options.get("global_scenery"))
    enrich_xp12 = bool(options.get("enrich_xp12", False))
    if global_scenery:
        enrich_xp12 = _prompt_bool("Enrich XP12 rasters", enrich_xp12)
    profile = _prompt_bool("Profile build", bool(options.get("profile", False)))
    metrics_json = options.get("metrics_json")
    if profile:
        metrics_json = _prompt_optional_str("Metrics JSON path", metrics_json)
    bundle_diagnostics = _prompt_bool(
        "Bundle diagnostics",
        bool(options.get("bundle_diagnostics", False)),
    )
    dry_run = _prompt_bool("Dry run (plan only)", bool(options.get("dry_run", False)))

    if runner_cmd and persist_config and "--persist-config" not in runner_cmd:
        runner_cmd.append("--persist-config")

    options = {
        **options,
        "quality": quality,
        "density": density,
        "autoortho": autoortho,
        "normalize": not skip_normalize,
        "runner": runner_cmd,
        "dsftool": dsftool_cmd,
        "target_crs": target_crs,
        "target_resolution": target_resolution,
        "resampling": resampling,
        "dst_nodata": dst_nodata,
        "fill_strategy": fill_strategy,
        "fill_value": fill_value,
        "fallback_dem_paths": fallback_dem_paths,
        "mosaic_strategy": mosaic_strategy,
        "normalized_compression": normalized_compression,
        "cache_sha256": cache_sha256,
        "tile_jobs": tile_jobs,
        "continue_on_error": continue_on_error,
        "coverage_min": coverage_min,
        "coverage_hard_fail": coverage_hard_fail,
        "coverage_metrics": coverage_metrics,
        "triangle_warn": triangle_warn,
        "triangle_max": triangle_max,
        "allow_triangle_overage": allow_triangle_overage,
        "global_scenery": global_scenery or None,
        "enrich_xp12": enrich_xp12 if global_scenery else False,
        "runner_timeout": runner_timeout,
        "runner_retries": runner_retries,
        "runner_stream_logs": runner_stream_logs,
        "dsftool_timeout": dsftool_timeout,
        "dsftool_retries": dsftool_retries,
        "profile": profile,
        "metrics_json": metrics_json if profile else None,
        "bundle_diagnostics": bundle_diagnostics,
        "dry_run": dry_run,
    }
    run_build(
        dem_paths=[Path(path) for path in (dem_paths or [])],
        tiles=tiles,
        backend_name="ortho4xp",
        output_dir=output_dir,
        options=options,
    )
