"""Interactive wizard for build configuration."""

from __future__ import annotations

import math
import os
import shlex
from pathlib import Path
from typing import Any, Mapping

from dem2dsf.build import run_build
from dem2dsf.dem.info import inspect_dem
from dem2dsf.dem.models import DemInfo
from dem2dsf.dem.stack import load_dem_stack
from dem2dsf.density import DENSITY_PRESETS
from dem2dsf.tile_inference import infer_tiles

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


def _resolution_to_meters(info: DemInfo) -> float | None:
    if info.crs is None:
        return None
    res_x, res_y = info.resolution
    if info.crs.upper() in {"EPSG:4326", "EPSG:4258"}:
        mid_lat = (info.bounds[1] + info.bounds[3]) / 2.0
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(mid_lat))
        if meters_per_deg_lon <= 0:
            meters_per_deg_lon = meters_per_deg_lat
        return max(res_x * meters_per_deg_lon, res_y * meters_per_deg_lat)
    return max(res_x, res_y)


def _recommend_density(infos: list[DemInfo]) -> str | None:
    resolutions = [value for info in infos if (value := _resolution_to_meters(info))]
    if not resolutions:
        return None
    resolution = min(resolutions)
    if resolution <= 5:
        return "ultra"
    if resolution <= 15:
        return "high"
    if resolution <= 30:
        return "medium"
    return "low"


def _recommend_target_resolution(infos: list[DemInfo]) -> float | None:
    resolutions = [value for info in infos if (value := _resolution_to_meters(info))]
    if not resolutions:
        return None
    return min(resolutions)


def _inspect_dem_paths(paths: list[Path]) -> list[DemInfo]:
    infos: list[DemInfo] = []
    for path in paths:
        if not path.exists():
            print(f"Warning: DEM not found for inspection: {path}")
            continue
        infos.append(inspect_dem(path, sample=True))
    return infos


def _dem_warnings(info: DemInfo) -> list[str]:
    warnings: list[str] = []
    if info.crs is None:
        warnings.append(f"{info.path}: missing CRS (assume EPSG:4326 or override).")
    if info.nodata is None:
        warnings.append(f"{info.path}: missing nodata (AOI masking needs one).")
    if info.vertical_units and info.vertical_units.lower() not in {"m", "meter", "meters"}:
        warnings.append(f"{info.path}: vertical units look non-metric ({info.vertical_units}).")
    resolution = _resolution_to_meters(info)
    if resolution is not None and resolution < 1:
        warnings.append(f"{info.path}: very fine resolution (~{resolution:.2f}m).")
    if resolution is not None and resolution > 500:
        warnings.append(f"{info.path}: very coarse resolution (~{resolution:.1f}m).")
    if info.min_elevation is not None and info.max_elevation is not None:
        if info.min_elevation < -1000 or info.max_elevation > 9000:
            warnings.append(
                f"{info.path}: elevation range {info.min_elevation:.1f}.."
                f"{info.max_elevation:.1f} looks suspect."
            )
    if info.nan_ratio is not None and info.nan_ratio > 0.01:
        warnings.append(f"{info.path}: {info.nan_ratio:.1%} NaN samples detected.")
    if info.nodata_ratio is not None and info.nodata_ratio > 0.2:
        warnings.append(f"{info.path}: {info.nodata_ratio:.1%} nodata coverage in sample.")
    return warnings


def _print_dem_summary(infos: list[DemInfo]) -> None:
    for info in infos:
        print(f"DEM: {info.path}")
        print(f"  CRS: {info.crs or 'missing'}")
        print(f"  Bounds: {info.bounds}")
        print(f"  Resolution: {info.resolution}")
        print(f"  Nodata: {info.nodata}")
        print(f"  Dtype: {info.dtype}")
        if info.vertical_units:
            print(f"  Vertical units: {info.vertical_units}")
        if info.min_elevation is not None and info.max_elevation is not None:
            print(f"  Elevation range: {info.min_elevation:.1f}..{info.max_elevation:.1f}")


def _print_tile_estimates(tiles: list[str], coverage: dict[str, float]) -> None:
    if not tiles:
        return
    print("Inferred tiles (coverage estimates):")
    limit = 20
    for index, tile in enumerate(tiles):
        if index >= limit:
            print(f"  ... and {len(tiles) - limit} more")
            break
        ratio = coverage.get(tile, 0.0)
        print(f"  {tile}: {ratio:.1%}")


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
    aoi_path = options.get("aoi")
    aoi_crs = options.get("aoi_crs")
    infer_tiles_flag = bool(options.get("infer_tiles", False))
    if defaults:
        if not tiles:
            if not infer_tiles_flag:
                raise ValueError("Defaults mode requires --tile values or --infer-tiles.")
            if not dem_paths and not stack_path:
                raise ValueError("Defaults mode requires --dem or --dem-stack values.")
            dem_path_list = [Path(path) for path in (dem_paths or [])]
            if not dem_path_list and stack_path:
                stack = load_dem_stack(Path(stack_path))
                dem_path_list = [layer.path for layer in stack.layers]
            inference = infer_tiles(
                dem_path_list,
                aoi_path=Path(aoi_path) if aoi_path else None,
                aoi_crs=aoi_crs,
            )
            tiles = inference.tiles
            if not tiles:
                raise ValueError("Defaults mode could not infer any tiles.")
        if not dem_paths and not stack_path:
            raise ValueError("Defaults mode requires --dem or --dem-stack values.")
        run_build(
            dem_paths=[Path(path) for path in (dem_paths or [])],
            tiles=tiles,
            backend_name="ortho4xp",
            output_dir=output_dir,
            options={**options, "aoi": aoi_path, "aoi_crs": aoi_crs},
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
    if not dem_paths and not stack_path:
        raise ValueError("Wizard requires DEMs or a DEM stack.")

    if not aoi_path:
        aoi_input = _prompt_optional_str("AOI path (optional)", None)
        if aoi_input:
            aoi_path = aoi_input
    if aoi_path and not aoi_crs:
        aoi_crs = _prompt_optional_str(
            "AOI CRS (blank assumes EPSG:4326, preferred)",
            None,
        )

    dem_path_list = [Path(path) for path in (dem_paths or [])]
    if not dem_path_list and stack_path:
        stack = load_dem_stack(Path(stack_path))
        dem_path_list = [layer.path for layer in stack.layers]

    if dem_path_list:
        infos = _inspect_dem_paths(dem_path_list)
        _print_dem_summary(infos)
        warnings: list[str] = []
        for info in infos:
            warnings.extend(_dem_warnings(info))
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"  {warning}")
        density_default = _recommend_density(infos) or options.get("density", "medium")
        if density_default != options.get("density", "medium"):
            print(f"Recommended density preset: {density_default}")
        target_resolution_default = options.get("target_resolution")
        recommended_resolution = _recommend_target_resolution(infos)
        if target_resolution_default is None and recommended_resolution is not None:
            target_resolution_default = recommended_resolution
            print(f"Suggested target resolution: {recommended_resolution:.1f}m")
    else:
        density_default = options.get("density", "medium")
        target_resolution_default = options.get("target_resolution")

    if not tiles and infer_tiles_flag:
        inference = infer_tiles(
            dem_path_list,
            aoi_path=Path(aoi_path) if aoi_path else None,
            aoi_crs=aoi_crs,
        )
        for warning in inference.warnings:
            print(f"Warning: {warning}")
        _print_tile_estimates(inference.tiles, inference.coverage)
        if _prompt_bool("Use inferred tiles", True):
            tiles = inference.tiles
    if not tiles:
        tiles = _prompt_list("Enter tile name(s), comma-separated: ")
    if not tiles:
        raise ValueError("Wizard requires tiles.")

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
    ddstool_cmd = _prompt_command(
        "DDSTool command override (blank for defaults)",
        options.get("ddstool"),
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
    dsf_validation = _prompt_choice(
        "DSF validation mode",
        ("roundtrip", "bounds", "none"),
        options.get("dsf_validation", "roundtrip"),
    )
    dsf_validation_workers = _prompt_optional_int(
        "DSF validation workers (blank = cores/2)",
        options.get("dsf_validation_workers"),
    )
    validate_all = _prompt_bool(
        "Validate all tiles (including warning/error tiles)",
        bool(options.get("validate_all", False)),
    )
    dds_validation = _prompt_choice(
        "DDS validation mode",
        ("none", "header", "ddstool"),
        options.get("dds_validation", "none"),
    )
    dds_strict = _prompt_bool(
        "Fail DDS validation on errors",
        bool(options.get("dds_strict", False)),
    )

    quality = _prompt_choice(
        "Raster quality",
        ("compat", "xp12-enhanced"),
        options.get("quality", "compat"),
    )
    density = _prompt_choice(
        "Density preset",
        tuple(DENSITY_PRESETS.keys()),
        density_default,
    )
    autoortho = _prompt_bool(
        "Enable AutoOrtho mode (skip downloads)",
        bool(options.get("autoortho", False)),
    )
    autoortho_texture_strict = bool(options.get("autoortho_texture_strict", False))
    if autoortho:
        autoortho_texture_strict = _prompt_bool(
            "Fail on missing/invalid AutoOrtho textures",
            autoortho_texture_strict,
        )
    else:
        autoortho_texture_strict = False
    skip_normalize = _prompt_bool(
        "Skip DEM normalization",
        not bool(options.get("normalize", True)),
    )
    target_crs = options.get("target_crs") or "EPSG:4326"
    resampling = options.get("resampling", "bilinear")
    target_resolution = target_resolution_default
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
    xp12_strict = bool(options.get("xp12_strict", False))
    if global_scenery:
        xp12_strict = _prompt_bool(
            "Fail when XP12 rasters are missing",
            xp12_strict,
        )
    else:
        xp12_strict = False
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
        "ddstool": ddstool_cmd,
        "dsf_validation": dsf_validation,
        "dsf_validation_workers": dsf_validation_workers,
        "validate_all": validate_all,
        "dds_validation": dds_validation,
        "dds_strict": dds_strict,
        "aoi": aoi_path,
        "aoi_crs": aoi_crs,
        "infer_tiles": infer_tiles_flag,
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
        "xp12_strict": xp12_strict if global_scenery else False,
        "autoortho_texture_strict": autoortho_texture_strict,
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
