"""Build orchestration: normalization, backend execution, and validation."""

from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping

import rasterio

from dem2dsf.autoortho import scan_terrain_textures
from dem2dsf.backends.base import BackendSpec, BuildRequest, BuildResult
from dem2dsf.backends.registry import get_backend
from dem2dsf.build_config import build_config_lock
from dem2dsf.contracts import validate_build_plan, validate_build_report
from dem2dsf.dem.adapter import profile_for_backend
from dem2dsf.dem.cache import (
    CACHE_VERSION,
    NormalizationCache,
    SourceFingerprint,
    fingerprint_path_map,
    fingerprint_paths,
    load_normalization_cache,
    write_normalization_cache,
)
from dem2dsf.dem.info import inspect_dem
from dem2dsf.dem.models import CoverageMetrics
from dem2dsf.dem.pipeline import normalize_for_tiles, normalize_stack_for_tiles
from dem2dsf.dem.stack import load_dem_stack, stack_to_options
from dem2dsf.dem.tiling import tile_bounds, tile_bounds_in_crs
from dem2dsf.density import triangle_limits_for_preset
from dem2dsf.diagnostics import bundle_diagnostics, default_bundle_path
from dem2dsf.dsf import (
    compare_bounds,
    expected_bounds_for_tile,
    parse_bounds,
    parse_properties_from_file,
)
from dem2dsf.perf import PerfTracker, resolve_metrics_path
from dem2dsf.provenance import PROVENANCE_LEVELS, build_provenance
from dem2dsf.reporting import build_plan, build_report
from dem2dsf.tools.ddstool import dds_header_ok, ddstool_info
from dem2dsf.tools.dsftool import dsf_to_text, roundtrip_dsf
from dem2dsf.triangles import estimate_triangles_from_raster
from dem2dsf.xp12 import enrich_dsf_rasters, find_global_dsf, inventory_dsf_rasters
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path
from dem2dsf.xplane_paths import parse_tile


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON payload to disk, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _resume_ok_tiles(report: Mapping[str, Any]) -> set[str]:
    tiles = set()
    for tile_entry in report.get("tiles", []):
        if not isinstance(tile_entry, dict):
            continue
        tile = tile_entry.get("tile")
        if tile and tile_entry.get("status") == "ok":
            tiles.add(str(tile))
    return tiles


def _normalize_command(value: object) -> list[str] | None:
    """Normalize a command input into a list of strings."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    raise TypeError("Command must be a string or list of strings.")


def _normalization_cache_options(
    *,
    target_crs: str,
    resampling: str,
    dst_nodata: float | None,
    resolution: tuple[float, float] | None,
    fill_strategy: str,
    fill_value: float,
    backend_profile: object | None,
    dem_stack: Mapping[str, Any] | None,
    aoi: str | None,
    aoi_crs: str | None,
    mosaic_strategy: str,
    normalized_compression: str | None,
) -> dict[str, Any]:
    """Return the normalized cache options payload."""
    return {
        "target_crs": target_crs,
        "resampling": resampling,
        "dst_nodata": dst_nodata,
        "resolution": list(resolution) if resolution else None,
        "fill_strategy": fill_strategy,
        "fill_value": fill_value,
        "backend_profile": getattr(backend_profile, "name", None),
        "dem_stack": dict(dem_stack) if dem_stack else None,
        "aoi": aoi,
        "aoi_crs": aoi_crs,
        "mosaic_strategy": mosaic_strategy,
        "normalized_compression": normalized_compression,
    }


def _build_normalization_cache(
    normalization: Any,
    *,
    options: Mapping[str, Any],
    fallback_sources: Iterable[Path],
    tiles: Iterable[str],
    compute_sha256: bool,
) -> NormalizationCache:
    """Build a NormalizationCache from a completed normalization pass."""
    tile_paths = {
        tile_result.tile: str(tile_result.path.resolve())
        for tile_result in normalization.tile_results
    }
    tile_fingerprints = fingerprint_path_map(
        {tile: Path(path) for tile, path in tile_paths.items()},
        compute_sha256=compute_sha256,
    )
    mosaic_path = Path(normalization.mosaic_path).resolve()
    mosaic_fingerprint = (
        SourceFingerprint.from_path(mosaic_path, compute_sha256=compute_sha256)
        if mosaic_path.exists()
        else None
    )
    return NormalizationCache(
        version=CACHE_VERSION,
        sources=fingerprint_paths(normalization.sources, compute_sha256=compute_sha256),
        fallback_sources=fingerprint_paths(fallback_sources, compute_sha256=compute_sha256),
        options=dict(options),
        tiles=tuple(tiles),
        tile_paths=tile_paths,
        tile_fingerprints=tile_fingerprints,
        mosaic_path=str(mosaic_path),
        mosaic_fingerprint=mosaic_fingerprint,
        coverage=normalization.coverage,
    )


def _resolve_tool_command(value: object) -> list[str] | None:
    """Return a normalized tool command list."""
    command = _normalize_command(value)
    if not command:
        return None
    return command


def _dsftool_kwargs(options: Mapping[str, Any]) -> dict[str, Any]:
    """Build optional DSFTool keyword arguments from options."""
    kwargs: dict[str, Any] = {}
    timeout = options.get("dsftool_timeout")
    if timeout is not None:
        kwargs["timeout"] = timeout
    retries = int(options.get("dsftool_retries", 0) or 0)
    if retries:
        kwargs["retries"] = retries
    return kwargs


def _ensure_messages(tile_entry: dict[str, Any]) -> list[str]:
    """Ensure a tile entry has a mutable messages list."""
    messages = tile_entry.get("messages")
    if not isinstance(messages, list):
        messages = []
        tile_entry["messages"] = messages
    return messages


def _ensure_metrics(tile_entry: dict[str, Any]) -> dict[str, Any]:
    """Ensure a tile entry has a mutable metrics dict."""
    metrics = tile_entry.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
        tile_entry["metrics"] = metrics
    return metrics


def _ensure_reasons(tile_entry: dict[str, Any]) -> list[dict[str, str]]:
    """Ensure a tile entry has a mutable reasons list."""
    reasons = tile_entry.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
        tile_entry["reasons"] = reasons
    return reasons


def _tile_message(tile_entry: Mapping[str, Any], message: str) -> str:
    tile = tile_entry.get("tile")
    return f"{tile}: {message}" if tile else message


def _record_issue(
    tile_entry: dict[str, Any],
    *,
    code: str,
    message: str,
    severity: str,
    report: dict[str, Any] | None = None,
    include_report: bool = True,
) -> None:
    """Record a warning/error with a reason code on a tile entry."""
    _ensure_messages(tile_entry).append(message)
    _ensure_reasons(tile_entry).append({"code": code, "severity": severity})
    if severity == "error":
        _mark_error(tile_entry)
        if report is not None and include_report:
            report.setdefault("errors", []).append(_tile_message(tile_entry, message))
    elif severity == "warning":
        _mark_warning(tile_entry)
        if report is not None and include_report:
            report.setdefault("warnings", []).append(_tile_message(tile_entry, message))


def _note_reason(
    tile_entry: dict[str, Any],
    *,
    code: str,
    message: str,
    severity: str,
) -> None:
    """Attach a reason code without affecting report-level warnings/errors."""
    _ensure_messages(tile_entry).append(message)
    _ensure_reasons(tile_entry).append({"code": code, "severity": severity})


def _mark_warning(tile_entry: dict[str, Any]) -> None:
    """Promote a tile status to warning when appropriate."""
    if tile_entry.get("status") == "ok":
        tile_entry["status"] = "warning"


def _mark_error(tile_entry: dict[str, Any]) -> None:
    """Set a tile status to error."""
    if tile_entry.get("status") != "error":
        tile_entry["status"] = "error"


def _mean_tile_latitude(tiles: list[str]) -> float:
    """Compute the mean latitude across tile bounds."""
    if not tiles:
        return 0.0
    latitudes = []
    for tile in tiles:
        _, min_lat, _, max_lat = tile_bounds(tile)
        latitudes.append((min_lat + max_lat) / 2.0)
    return sum(latitudes) / len(latitudes)


def _resolution_from_options(
    options: Mapping[str, Any],
    tiles: list[str],
    target_crs: str,
) -> tuple[float, float] | None:
    """Derive target resolution from options and CRS heuristics."""
    target_resolution = options.get("target_resolution")
    if target_resolution is None:
        return None
    resolution_m = float(target_resolution)
    if resolution_m <= 0:
        raise ValueError("Target resolution must be positive.")
    if target_crs.upper() in {"EPSG:4326", "EPSG:4258"}:
        meters_per_deg_lat = 111_320.0
        avg_lat = _mean_tile_latitude(tiles)
        meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(avg_lat))
        if meters_per_deg_lon <= 0:
            meters_per_deg_lon = meters_per_deg_lat
        return (resolution_m / meters_per_deg_lon, resolution_m / meters_per_deg_lat)
    return (resolution_m, resolution_m)


def _validation_worker_limit(requested: int | None) -> int:
    max_workers = os.cpu_count() or 1
    if requested is None:
        return max(1, max_workers // 2)
    workers = int(requested)
    if workers < 1:
        raise ValueError("Validation workers must be >= 1.")
    return min(workers, max_workers)


def _dem_resolution_meters(info: object) -> float | None:
    crs = getattr(info, "crs", None)
    if crs is None:
        return None
    res_x, res_y = getattr(info, "resolution", (None, None))
    if res_x is None or res_y is None:
        return None
    if str(crs).upper() in {"EPSG:4326", "EPSG:4258"}:
        bounds = getattr(info, "bounds", None)
        if bounds:
            mid_lat = (bounds[1] + bounds[3]) / 2.0
            meters_per_deg_lat = 111_320.0
            meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(mid_lat))
            if meters_per_deg_lon <= 0:
                meters_per_deg_lon = meters_per_deg_lat
            return max(res_x * meters_per_deg_lon, res_y * meters_per_deg_lat)
    return max(res_x, res_y)


def _dem_sanity_findings(info: object) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    path = getattr(info, "path", "<dem>")
    crs = getattr(info, "crs", None)
    nodata = getattr(info, "nodata", None)
    vertical_units = getattr(info, "vertical_units", None)
    min_elevation = getattr(info, "min_elevation", None)
    max_elevation = getattr(info, "max_elevation", None)
    nan_ratio = getattr(info, "nan_ratio", None)
    nodata_ratio = getattr(info, "nodata_ratio", None)

    if crs is None:
        findings.append(
            (
                "dem_missing_crs",
                f"{path}: missing CRS (assume EPSG:4326 or override).",
            )
        )
    if nodata is None:
        findings.append(
            (
                "dem_missing_nodata",
                f"{path}: missing nodata (AOI masking and fills rely on it).",
            )
        )
    if vertical_units and str(vertical_units).lower() not in {"m", "meter", "meters"}:
        findings.append(
            (
                "dem_vertical_units_nonmetric",
                f"{path}: vertical units look non-metric ({vertical_units}).",
            )
        )
    resolution = _dem_resolution_meters(info)
    if resolution is not None and resolution < 1:
        findings.append(
            (
                "dem_resolution_fine",
                f"{path}: very fine resolution (~{resolution:.2f}m).",
            )
        )
    if resolution is not None and resolution > 500:
        findings.append(
            (
                "dem_resolution_coarse",
                f"{path}: very coarse resolution (~{resolution:.1f}m).",
            )
        )
    if min_elevation is not None and max_elevation is not None:
        if min_elevation < -1000 or max_elevation > 9000:
            findings.append(
                (
                    "dem_elevation_range_suspect",
                    (
                        f"{path}: elevation range "
                        f"{min_elevation:.1f}..{max_elevation:.1f} looks suspect."
                    ),
                )
            )
    if nan_ratio is not None and nan_ratio > 0.01:
        findings.append(
            (
                "dem_nan_ratio_high",
                f"{path}: {nan_ratio:.1%} NaN samples detected.",
            )
        )
    if nodata_ratio is not None and nodata_ratio > 0.2:
        findings.append(
            (
                "dem_nodata_ratio_high",
                f"{path}: {nodata_ratio:.1%} nodata coverage in sample.",
            )
        )
    return findings


def _apply_dem_sanity_checks(
    report: dict[str, Any],
    dem_paths: Iterable[Path],
) -> None:
    findings: list[dict[str, str]] = []
    for path in dem_paths:
        try:
            info = inspect_dem(path, sample=True)
        except Exception as exc:  # pragma: no cover - defensive guard
            findings.append(
                {
                    "path": str(path),
                    "code": "dem_inspect_failed",
                    "message": f"{path}: DEM inspection failed ({exc})",
                }
            )
            continue
        for code, message in _dem_sanity_findings(info):
            findings.append({"path": str(path), "code": code, "message": message})

    if not findings:
        return
    report.setdefault("artifacts", {})["dem_sanity"] = findings
    for item in findings:
        report.setdefault("warnings", []).append(item["message"])
    for tile_entry in report.get("tiles", []):
        for item in findings:
            _record_issue(
                tile_entry,
                code=item["code"],
                message=item["message"],
                severity="warning",
                report=report,
                include_report=False,
            )


def _normalize_compression(value: object) -> str | None:
    """Normalize compression option strings into GDAL-compatible values."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text == "none":
        return None
    if text in {"lzw", "deflate"}:
        return text.upper()
    raise ValueError("normalized_compression must be one of: none, lzw, deflate.")


def _format_bytes(value: float) -> str:
    """Format a byte count for display."""
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} B"


def _estimate_build_guardrails(
    tiles: list[str],
    *,
    target_crs: str,
    resolution: tuple[float, float] | None,
    options: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Estimate build sizes and return guardrail warnings."""
    if not tiles or resolution is None:
        return None, []
    try:
        crs = rasterio.CRS.from_string(target_crs)
    except (TypeError, ValueError):
        return None, []
    res_x, res_y = abs(resolution[0]), abs(resolution[1])
    if res_x <= 0 or res_y <= 0:
        return None, []

    max_width = 0
    max_height = 0
    max_pixels = 0
    total_pixels = 0
    for tile in tiles:
        min_x, min_y, max_x, max_y = tile_bounds_in_crs(tile, crs)
        width = max(1, int(math.ceil((max_x - min_x) / res_x)))
        height = max(1, int(math.ceil((max_y - min_y) / res_y)))
        pixels = width * height
        max_width = max(max_width, width)
        max_height = max(max_height, height)
        max_pixels = max(max_pixels, pixels)
        total_pixels += pixels

    triangles_per_tile = 0
    if max_width >= 2 and max_height >= 2:
        triangles_per_tile = (max_width - 1) * (max_height - 1) * 2
    triangles_total = triangles_per_tile * len(tiles)

    bytes_per_pixel = 4
    tile_bytes_estimate = max_pixels * bytes_per_pixel
    total_bytes_estimate = total_pixels * bytes_per_pixel

    warnings: list[str] = []
    pixel_warn_threshold = 200_000_000
    tile_bytes_warn_threshold = 512 * 1024 * 1024
    total_bytes_warn_threshold = 8 * 1024 * 1024 * 1024

    if max_pixels > pixel_warn_threshold:
        warnings.append(
            "Estimated tile grid "
            f"{max_width}x{max_height} (~{max_pixels:,} px) exceeds "
            f"{pixel_warn_threshold:,} px; consider higher target resolution."
        )
    if tile_bytes_estimate > tile_bytes_warn_threshold:
        warnings.append(
            "Estimated tile size "
            f"{_format_bytes(tile_bytes_estimate)} exceeds "
            f"{_format_bytes(tile_bytes_warn_threshold)}; expect heavy disk/RAM usage."
        )
    if total_bytes_estimate > total_bytes_warn_threshold:
        warnings.append(
            "Estimated normalized tiles "
            f"{_format_bytes(total_bytes_estimate)} exceeds "
            f"{_format_bytes(total_bytes_warn_threshold)}; consider splitting the build."
        )

    density = options.get("density", "medium")
    warn_limit = options.get("triangle_warn")
    max_limit = options.get("triangle_max")
    if warn_limit is None or max_limit is None:
        try:
            limits = triangle_limits_for_preset(density)
        except ValueError:
            limits = triangle_limits_for_preset("medium")
        warn_limit = warn_limit if warn_limit is not None else limits["warn"]
        max_limit = max_limit if max_limit is not None else limits["max"]

    if triangles_per_tile:
        if max_limit is not None and triangles_per_tile > max_limit:
            warnings.append(
                f"Estimated triangles per tile {triangles_per_tile:,} exceed max "
                f"{max_limit:,} before normalization."
            )
        elif warn_limit is not None and triangles_per_tile > warn_limit:
            warnings.append(
                f"Estimated triangles per tile {triangles_per_tile:,} exceed warn "
                f"{warn_limit:,} before normalization."
            )
        total_warn = warn_limit * len(tiles) if warn_limit is not None else None
        total_max = max_limit * len(tiles) if max_limit is not None else None
        if total_max is not None and triangles_total > total_max:
            warnings.append(
                f"Estimated total triangles {triangles_total:,} exceed {total_max:,} "
                f"across {len(tiles)} tiles."
            )
        elif total_warn is not None and triangles_total > total_warn:
            warnings.append(
                f"Estimated total triangles {triangles_total:,} exceed {total_warn:,} "
                f"across {len(tiles)} tiles."
            )

    estimates = {
        "tile_width": max_width,
        "tile_height": max_height,
        "tile_pixels": max_pixels,
        "tile_bytes_estimate": tile_bytes_estimate,
        "total_pixels": total_pixels,
        "total_bytes_estimate": total_bytes_estimate,
        "triangles_per_tile_estimate": triangles_per_tile,
        "triangles_total_estimate": triangles_total,
        "bytes_per_pixel_estimate": bytes_per_pixel,
        "resolution": [res_x, res_y],
        "tile_count": len(tiles),
    }
    return estimates, warnings


def _apply_coverage_metrics(report: dict[str, Any], coverage_metrics: Mapping[str, Any]) -> None:
    """Attach coverage metrics to the per-tile report entries."""
    if not coverage_metrics:
        return
    for tile_entry in report.get("tiles", []):
        tile = tile_entry.get("tile")
        if not tile:
            continue
        metrics = coverage_metrics.get(tile)
        if metrics is None:
            continue
        tile_metrics = _ensure_metrics(tile_entry)
        tile_metrics["coverage"] = {
            "total_pixels": metrics.total_pixels,
            "nodata_pixels_before": metrics.nodata_pixels_before,
            "nodata_pixels_after": metrics.nodata_pixels_after,
            "coverage_before": metrics.coverage_before,
            "coverage_after": metrics.coverage_after,
            "filled_pixels": metrics.filled_pixels,
            "strategy": metrics.strategy,
            "normalize_seconds": metrics.normalize_seconds,
        }


def _apply_coverage_thresholds(
    report: dict[str, Any],
    coverage_metrics: Mapping[str, CoverageMetrics],
    *,
    min_coverage: float | None,
    hard_fail: bool,
) -> None:
    """Apply coverage thresholds as warnings or errors."""
    if not coverage_metrics or min_coverage is None:
        return
    for tile_entry in report.get("tiles", []):
        tile = tile_entry.get("tile")
        if not tile:
            continue
        metrics = coverage_metrics.get(tile)
        if metrics is None:
            continue
        if metrics.coverage_before >= min_coverage:
            continue
        message = f"coverage_before {metrics.coverage_before:.2%} below {min_coverage:.2%}"
        _record_issue(
            tile_entry,
            code="coverage_below_min",
            message=message,
            severity="error" if hard_fail else "warning",
            report=report,
        )


def _validate_build_inputs(
    *,
    tiles: Iterable[str],
    dem_paths: Iterable[Path],
    options: Mapping[str, Any],
) -> None:
    """Validate build inputs and option guardrails."""
    tile_list = list(tiles)
    dem_list = list(dem_paths)
    dry_run = bool(options.get("dry_run", False))
    for tile in tile_list:
        parse_tile(tile)
    for path in dem_list:
        if not path.exists() and not dry_run:
            raise ValueError(f"DEM not found: {path}")
    aoi_path = options.get("aoi")
    if aoi_path and not dry_run and not Path(aoi_path).exists():
        raise ValueError(f"AOI not found: {aoi_path}")
    if not options.get("normalize", True):
        tile_dem_paths = options.get("tile_dem_paths") or {}
        tile_dem_complete = bool(tile_dem_paths) and all(
            tile in tile_dem_paths for tile in tile_list
        )
        if not tile_dem_complete:
            if options.get("dem_stack_path"):
                raise ValueError("Skipping normalization is not supported with DEM stacks.")
            if len(dem_list) != 1:
                raise ValueError("Skipping normalization requires exactly one DEM path.")
    coverage_min = options.get("coverage_min")
    if coverage_min is not None:
        if not 0.0 <= float(coverage_min) <= 1.0:
            raise ValueError("min_coverage must be between 0 and 1.")
    elif options.get("coverage_hard_fail"):
        raise ValueError("coverage_hard_fail requires min_coverage.")
    provenance_level = options.get("provenance_level", "basic")
    if provenance_level not in PROVENANCE_LEVELS:
        raise ValueError("provenance_level must be basic or strict.")


def _apply_triangle_guardrails(report: dict[str, Any], options: Mapping[str, Any]) -> None:
    """Estimate triangle counts and flag tiles over configured limits."""
    tile_dem_paths = options.get("tile_dem_paths") or {}
    density = options.get("density", "medium")
    warn_limit = options.get("triangle_warn")
    max_limit = options.get("triangle_max")
    allow_overage = bool(options.get("allow_triangle_overage", False))

    if warn_limit is None or max_limit is None:
        try:
            limits = triangle_limits_for_preset(density)
        except ValueError:
            limits = triangle_limits_for_preset("medium")
        warn_limit = warn_limit if warn_limit is not None else limits["warn"]
        max_limit = max_limit if max_limit is not None else limits["max"]

    for tile_entry in report.get("tiles", []):
        tile = tile_entry.get("tile")
        if not tile:
            continue
        dem_path = tile_dem_paths.get(tile)
        if not dem_path:
            continue
        estimate = estimate_triangles_from_raster(Path(dem_path))
        metrics = _ensure_metrics(tile_entry)
        metrics["triangles"] = {
            "estimated": estimate.count,
            "width": estimate.width,
            "height": estimate.height,
            "warn": warn_limit,
            "max": max_limit,
            "source": "dem-grid",
        }
        _ensure_messages(tile_entry).append(
            f"Triangle estimate: {estimate.count} (warn {warn_limit}, max {max_limit})"
        )
        if estimate.count > max_limit:
            message = f"Triangle estimate {estimate.count} exceeds max {max_limit}"
            _record_issue(
                tile_entry,
                code="triangle_over_max",
                message=message,
                severity="warning" if allow_overage else "error",
                report=report,
            )
        elif estimate.count > warn_limit:
            message = f"Triangle estimate {estimate.count} exceeds warn {warn_limit}"
            _record_issue(
                tile_entry,
                code="triangle_over_warn",
                message=message,
                severity="warning",
                report=report,
            )


def _apply_xp12_checks(
    report: dict[str, Any],
    options: Mapping[str, Any],
    output_dir: Path,
) -> None:
    """Inventory XP12 rasters in DSFs and record warnings/errors."""
    quality = options.get("quality", "compat")
    strict_required = bool(options.get("xp12_strict", False)) or quality == "xp12-enhanced"
    dsftool_cmd = _resolve_tool_command(options.get("dsftool"))
    global_scenery = options.get("global_scenery")
    global_root = Path(global_scenery) if global_scenery else None
    dsftool_kwargs = _dsftool_kwargs(options)

    for tile_entry in report.get("tiles", []):
        tile = tile_entry.get("tile")
        if not tile:
            continue
        dsf_path = xplane_dsf_path(output_dir, tile)
        if not dsf_path.exists():
            _record_issue(
                tile_entry,
                code="xp12_dsf_missing",
                message="DSF output not found; XP12 raster check skipped.",
                severity="error" if strict_required else "warning",
                report=report,
            )
            continue
        if not dsftool_cmd:
            message = "DSFTool not configured; XP12 raster check skipped."
            _record_issue(
                tile_entry,
                code="xp12_dsftool_missing",
                message=message,
                severity="error" if strict_required else "warning",
                report=report,
            )
            continue

        try:
            summary = inventory_dsf_rasters(
                dsftool_cmd,
                dsf_path,
                output_dir / "xp12" / tile,
                **dsftool_kwargs,
            )
        except RuntimeError as exc:
            _record_issue(
                tile_entry,
                code="xp12_inventory_failed",
                message=str(exc),
                severity="error",
                report=report,
            )
            continue

        metrics = _ensure_metrics(tile_entry)
        metrics["xp12_rasters"] = {
            "soundscape_present": summary.soundscape_present,
            "season_raster_count": summary.season_raster_count,
            "season_raster_expected": summary.season_raster_expected,
            "rasters": list(summary.raster_names),
        }

        missing = []
        if not summary.soundscape_present:
            missing.append("soundscape")
        if summary.season_raster_count < summary.season_raster_expected:
            missing.append("seasons")
        if missing:
            message = f"XP12 rasters missing: {', '.join(missing)}"
            metrics["xp12_rasters"]["missing_required"] = missing
            _record_issue(
                tile_entry,
                code="xp12_rasters_missing",
                message=message,
                severity="error" if strict_required else "warning",
                report=report,
            )
        if global_root:
            candidate = find_global_dsf(global_root, tile)
            if candidate:
                _ensure_messages(tile_entry).append(f"Global scenery candidate: {candidate}")


def _apply_xp12_enrichment(
    report: dict[str, Any],
    options: Mapping[str, Any],
    output_dir: Path,
) -> None:
    """Try to enrich DSFs with XP12 rasters from global scenery."""
    if not options.get("enrich_xp12"):
        return

    dsftool_cmd = _resolve_tool_command(options.get("dsftool"))
    global_scenery = options.get("global_scenery")
    global_root = Path(global_scenery) if global_scenery else None
    dsftool_kwargs = _dsftool_kwargs(options)

    if not dsftool_cmd or not global_root:
        message = "XP12 enrichment requires --dsftool and --global-scenery."
        for tile_entry in report.get("tiles", []):
            _record_issue(
                tile_entry,
                code="xp12_enrichment_missing_tools",
                message=message,
                severity="error",
                report=report,
                include_report=False,
            )
        report.setdefault("errors", []).append(message)
        return

    for tile_entry in report.get("tiles", []):
        tile = tile_entry.get("tile")
        if not tile:
            continue
        dsf_path = xplane_dsf_path(output_dir, tile)
        if not dsf_path.exists():
            _record_issue(
                tile_entry,
                code="xp12_enrichment_dsf_missing",
                message="DSF output not found; XP12 enrichment skipped.",
                severity="warning",
                report=report,
            )
            continue
        global_dsf = find_global_dsf(global_root, tile)
        if not global_dsf:
            _record_issue(
                tile_entry,
                code="xp12_enrichment_global_missing",
                message="Global scenery DSF not found; XP12 enrichment skipped.",
                severity="warning",
                report=report,
            )
            continue

        result = enrich_dsf_rasters(
            dsftool_cmd,
            dsf_path,
            global_dsf,
            output_dir / "xp12" / tile / "enrich",
            **dsftool_kwargs,
        )
        metrics = _ensure_metrics(tile_entry)
        metrics["xp12_enrichment"] = {
            "status": result.status,
            "missing": list(result.missing),
            "added": list(result.added),
            "backup_path": result.backup_path,
            "enriched_text_path": result.enriched_text_path,
            "global_dsf": str(global_dsf),
            "error": result.error,
        }
        if result.status == "failed":
            _record_issue(
                tile_entry,
                code="xp12_enrichment_failed",
                message=f"XP12 enrichment failed: {result.error}",
                severity="error",
                report=report,
            )
            continue
        if result.status == "no-op":
            _ensure_messages(tile_entry).append(
                "XP12 enrichment not needed; rasters already present."
            )
            continue
        if result.status == "enriched":
            _ensure_messages(tile_entry).append(f"XP12 rasters enriched: {', '.join(result.added)}")
            try:
                summary = inventory_dsf_rasters(
                    dsftool_cmd,
                    dsf_path,
                    output_dir / "xp12" / tile / "post",
                    **dsftool_kwargs,
                )
                metrics["xp12_rasters_after"] = {
                    "soundscape_present": summary.soundscape_present,
                    "season_raster_count": summary.season_raster_count,
                    "season_raster_expected": summary.season_raster_expected,
                    "rasters": list(summary.raster_names),
                }
            except RuntimeError as exc:
                _record_issue(
                    tile_entry,
                    code="xp12_enrichment_postcheck_failed",
                    message=str(exc),
                    severity="warning",
                    report=report,
                )


def _apply_autoortho_checks(
    report: dict[str, Any],
    options: Mapping[str, Any],
    output_dir: Path,
) -> None:
    """Scan terrain textures for AutoOrtho compatibility issues."""
    if not options.get("autoortho"):
        return

    textures = scan_terrain_textures(output_dir)
    strict = bool(options.get("autoortho_texture_strict", False))
    report.setdefault("artifacts", {})["autoortho"] = {
        "referenced": list(textures.referenced),
        "missing": list(textures.missing),
        "invalid": list(textures.invalid),
        "guidance": (
            "AutoOrtho expects Ortho4XP texture naming and skip_downloads in Ortho4XP config."
        ),
    }
    summary = (
        f"AutoOrtho textures: {len(textures.invalid)} invalid, {len(textures.missing)} missing."
    )
    for tile_entry in report.get("tiles", []):
        _ensure_messages(tile_entry).append(summary)
        if textures.invalid or textures.missing:
            _mark_error(tile_entry) if strict else _mark_warning(tile_entry)

    severity = "error" if strict else "warning"
    if textures.invalid:
        message = f"AutoOrtho invalid texture refs: {', '.join(textures.invalid[:5])}"
        report.setdefault("errors" if strict else "warnings", []).append(message)
        for tile_entry in report.get("tiles", []):
            _record_issue(
                tile_entry,
                code="autoortho_invalid_textures",
                message=message,
                severity=severity,
                report=report,
                include_report=False,
            )
    if textures.missing:
        message = f"AutoOrtho missing texture refs: {', '.join(textures.missing[:5])}"
        report.setdefault("errors" if strict else "warnings", []).append(message)
        for tile_entry in report.get("tiles", []):
            _record_issue(
                tile_entry,
                code="autoortho_missing_textures",
                message=message,
                severity=severity,
                report=report,
                include_report=False,
            )


def _collect_dds_paths(output_dir: Path) -> list[Path]:
    textures_dir = output_dir / "textures"
    if not textures_dir.exists():
        return []
    return sorted(
        path for path in textures_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".dds"
    )


def _apply_dds_validation(
    report: dict[str, Any],
    options: Mapping[str, Any],
    output_dir: Path,
) -> None:
    mode = options.get("dds_validation", "none")
    if mode == "none":
        return
    if mode not in {"header", "ddstool"}:
        raise ValueError(f"Unsupported DDS validation mode: {mode}")
    strict = bool(options.get("dds_strict", False))
    ddstool_cmd = _resolve_tool_command(options.get("ddstool"))
    if mode == "ddstool" and not ddstool_cmd:
        message = "DDSTool not configured; DDS validation skipped."
        for tile_entry in report.get("tiles", []):
            _record_issue(
                tile_entry,
                code="dds_validation_missing_ddstool",
                message=message,
                severity="error" if strict else "warning",
                report=report,
                include_report=False,
            )
        report.setdefault("errors" if strict else "warnings", []).append(message)
        return

    dds_paths = _collect_dds_paths(output_dir)
    if not dds_paths:
        message = "No DDS textures found; DDS validation skipped."
        for tile_entry in report.get("tiles", []):
            _record_issue(
                tile_entry,
                code="dds_validation_no_textures",
                message=message,
                severity="warning",
                report=report,
                include_report=False,
            )
        report.setdefault("warnings", []).append(message)
        return

    invalid_headers: list[str] = []
    ddstool_failures: list[str] = []
    for texture_path in dds_paths:
        if not dds_header_ok(texture_path):
            invalid_headers.append(str(texture_path))
        if mode == "ddstool" and ddstool_cmd:
            try:
                ddstool_info(ddstool_cmd, texture_path)
            except RuntimeError as exc:
                ddstool_failures.append(f"{texture_path}: {exc}")

    report.setdefault("artifacts", {})["dds_validation"] = {
        "mode": mode,
        "texture_count": len(dds_paths),
        "invalid_headers": invalid_headers,
        "ddstool_failures": ddstool_failures,
    }
    summary = (
        f"DDS validation ({mode}): {len(dds_paths)} texture(s), "
        f"{len(invalid_headers)} invalid headers, {len(ddstool_failures)} ddstool failures."
    )
    for tile_entry in report.get("tiles", []):
        _ensure_messages(tile_entry).append(summary)

    severity = "error" if strict else "warning"
    if invalid_headers:
        message = f"DDS header invalid for: {', '.join(invalid_headers[:5])}"
        report.setdefault("errors" if strict else "warnings", []).append(message)
        for tile_entry in report.get("tiles", []):
            _record_issue(
                tile_entry,
                code="dds_validation_invalid_header",
                message=message,
                severity=severity,
                report=report,
                include_report=False,
            )
    if ddstool_failures:
        message = f"DDSTool failed for: {', '.join(ddstool_failures[:3])}"
        report.setdefault("errors" if strict else "warnings", []).append(message)
        for tile_entry in report.get("tiles", []):
            _record_issue(
                tile_entry,
                code="dds_validation_ddstool_failed",
                message=message,
                severity=severity,
                report=report,
                include_report=False,
            )


def _apply_dsf_validation(
    report: dict[str, Any],
    options: Mapping[str, Any],
    output_dir: Path,
) -> None:
    """Validate DSF structure and geographic bounds."""
    mode = options.get("dsf_validation", "roundtrip")
    if mode == "none":
        return
    if mode not in {"bounds", "roundtrip"}:
        raise ValueError(f"Unsupported DSF validation mode: {mode}")
    validate_all = bool(options.get("validate_all", False))
    dsftool_cmd = _resolve_tool_command(options.get("dsftool"))
    dsftool_kwargs = _dsftool_kwargs(options)
    if not dsftool_cmd:
        message = "DSFTool not configured; DSF validation skipped."
        for tile_entry in report.get("tiles", []):
            _record_issue(
                tile_entry,
                code="dsf_validation_missing_dsftool",
                message=message,
                severity="warning",
                report=report,
                include_report=False,
            )
        report.setdefault("warnings", []).append(message)
        return

    tile_entries = {
        tile_entry.get("tile"): tile_entry
        for tile_entry in report.get("tiles", [])
        if tile_entry.get("tile")
    }
    tasks: list[tuple[str, Path]] = []
    for tile, tile_entry in tile_entries.items():
        status = tile_entry.get("status")
        if not validate_all and status in {"warning", "error", "skipped"}:
            _note_reason(
                tile_entry,
                code="dsf_validation_skipped",
                message="DSF validation skipped due to tile status.",
                severity="warning",
            )
            continue
        dsf_path = xplane_dsf_path(output_dir, tile)
        if not dsf_path.exists():
            _record_issue(
                tile_entry,
                code="dsf_validation_missing_dsf",
                message="DSF output not found; DSF validation skipped.",
                severity="warning",
                report=report,
            )
            continue
        tasks.append((tile, dsf_path))

    if not tasks:
        return

    def run_validation(tile: str, dsf_path: Path) -> dict[str, Any]:
        work_dir = output_dir / "dsf_validation" / tile
        work_dir.mkdir(parents=True, exist_ok=True)
        text_path = work_dir / f"{dsf_path.stem}.txt"
        rebuilt_path = work_dir / dsf_path.name
        validation_metrics: dict[str, Any] = {
            "mode": mode,
            "text_path": str(text_path),
        }
        messages: list[str] = []
        reasons: list[dict[str, str]] = []
        errors: list[str] = []
        warnings: list[str] = []
        status: str | None = None

        def add_issue(severity: str, code: str, message: str) -> None:
            nonlocal status
            messages.append(message)
            reasons.append({"code": code, "severity": severity})
            if severity == "error":
                status = "error"
                errors.append(f"{tile}: {message}")
            elif severity == "warning":
                if status != "error":
                    status = "warning"
                warnings.append(f"{tile}: {message}")

        if mode == "roundtrip":
            validation_metrics["roundtrip"] = "pending"
            validation_metrics["rebuilt_path"] = str(rebuilt_path)
            try:
                roundtrip_dsf(
                    dsftool_cmd,
                    dsf_path,
                    work_dir,
                    **dsftool_kwargs,
                )
            except RuntimeError as exc:
                message = str(exc)
                validation_metrics["roundtrip"] = "failed"
                validation_metrics["error"] = message
                add_issue("error", "dsf_validation_roundtrip_failed", message)
                return {
                    "tile": tile,
                    "messages": messages,
                    "reasons": reasons,
                    "metrics": validation_metrics,
                    "status": status,
                    "errors": errors,
                    "warnings": warnings,
                }
            validation_metrics["roundtrip"] = "ok"
        else:
            validation_metrics["roundtrip"] = "skipped"
            try:
                dsf_to_text(
                    dsftool_cmd,
                    dsf_path,
                    text_path,
                    **dsftool_kwargs,
                )
            except RuntimeError as exc:
                message = str(exc)
                validation_metrics["roundtrip"] = "failed"
                validation_metrics["error"] = message
                add_issue("error", "dsf_validation_dsf2text_failed", message)
                return {
                    "tile": tile,
                    "messages": messages,
                    "reasons": reasons,
                    "metrics": validation_metrics,
                    "status": status,
                    "errors": errors,
                    "warnings": warnings,
                }

        try:
            properties = parse_properties_from_file(text_path)
            actual_bounds = parse_bounds(properties)
        except ValueError as exc:
            message = f"DSF bounds parse failed: {exc}"
            validation_metrics["bounds_error"] = str(exc)
            add_issue("error", "dsf_validation_bounds_parse_failed", message)
            return {
                "tile": tile,
                "messages": messages,
                "reasons": reasons,
                "metrics": validation_metrics,
                "status": status,
                "errors": errors,
                "warnings": warnings,
            }
        expected_bounds = expected_bounds_for_tile(tile)
        mismatches = compare_bounds(expected_bounds, actual_bounds)
        validation_metrics["bounds"] = {
            "expected": expected_bounds.__dict__,
            "actual": actual_bounds.__dict__,
            "mismatches": mismatches,
        }
        if mismatches:
            message = f"DSF bounds mismatch: {', '.join(mismatches)}"
            add_issue("error", "dsf_validation_bounds_mismatch", message)
        return {
            "tile": tile,
            "messages": messages,
            "reasons": reasons,
            "metrics": validation_metrics,
            "status": status,
            "errors": errors,
            "warnings": warnings,
        }

    def apply_outcome(outcome: dict[str, Any]) -> None:
        tile = outcome["tile"]
        tile_entry = tile_entries.get(tile)
        if not tile_entry:
            return
        _ensure_messages(tile_entry).extend(outcome["messages"])
        _ensure_reasons(tile_entry).extend(outcome["reasons"])
        metrics = _ensure_metrics(tile_entry)
        metrics["dsf_validation"] = outcome["metrics"]
        status = outcome["status"]
        if status == "error":
            _mark_error(tile_entry)
        elif status == "warning":
            _mark_warning(tile_entry)
        if outcome["errors"]:
            report.setdefault("errors", []).extend(outcome["errors"])
        if outcome["warnings"]:
            report.setdefault("warnings", []).extend(outcome["warnings"])

    worker_limit = _validation_worker_limit(options.get("dsf_validation_workers"))
    if worker_limit <= 1 or len(tasks) == 1:
        for tile, dsf_path in tasks:
            apply_outcome(run_validation(tile, dsf_path))
    else:
        with ThreadPoolExecutor(max_workers=worker_limit) as executor:
            futures = {
                executor.submit(run_validation, tile, dsf_path): tile for tile, dsf_path in tasks
            }
            for future in as_completed(futures):
                apply_outcome(future.result())


def _attach_performance(
    report: dict[str, Any],
    perf: PerfTracker,
    output_dir: Path,
    options: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach performance metrics to a report and write metrics output."""
    if not perf.enabled:
        return report
    summary = perf.summary()
    report = {**report, "performance": summary}
    metrics_path = resolve_metrics_path(output_dir, options.get("metrics_json"))
    if metrics_path:
        write_json(metrics_path, summary)
    return report


def _finalize_result(
    result: BuildResult,
    *,
    perf: PerfTracker,
    output_dir: Path,
    options: Mapping[str, Any],
) -> BuildResult:
    if result is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Build did not produce a report.")

    report = _attach_performance(dict(result.build_report), perf, output_dir, options)
    inputs = result.build_plan.get("inputs") if result.build_plan else None
    if inputs:
        report = {**report, "inputs": inputs}
    result = BuildResult(build_plan=result.build_plan, build_report=report)
    bundle_path = None
    if options.get("bundle_diagnostics"):
        bundle_path = default_bundle_path(output_dir)
        report_artifacts = dict(result.build_report.get("artifacts", {}))
        report_artifacts["diagnostics_bundle"] = str(bundle_path)
        report_with_bundle = {**result.build_report, "artifacts": report_artifacts}
        result = BuildResult(build_plan=result.build_plan, build_report=report_with_bundle)
    validate_build_plan(result.build_plan)
    validate_build_report(result.build_report)
    write_json(output_dir / "build_plan.json", result.build_plan)
    write_json(output_dir / "build_report.json", result.build_report)
    if bundle_path is not None:
        try:
            bundle_diagnostics(output_dir, output_path=bundle_path)
        except FileNotFoundError:
            pass
    return result


def _resume_validation(
    *,
    dem_paths: list[Path],
    tiles: list[str],
    backend_spec: BackendSpec,
    output_dir: Path,
    options: Mapping[str, Any],
    perf: PerfTracker,
) -> BuildResult:
    previous_report = _load_json(output_dir / "build_report.json")
    if previous_report is None:
        raise ValueError("resume validation-only requires an existing build_report.json")
    previous_plan = _load_json(output_dir / "build_plan.json") or {}

    if not tiles:
        tiles = []
        for entry in previous_report.get("tiles", []):
            if not isinstance(entry, dict):
                continue
            tile = entry.get("tile")
            if isinstance(tile, str) and tile:
                tiles.append(tile)
    if not tiles:
        raise ValueError("resume validation-only requires tiles in build_report.json")

    if not dem_paths:
        dem_inputs = previous_plan.get("inputs", {}).get("dems", [])
        if isinstance(dem_inputs, list):
            dem_paths = [Path(path) for path in dem_inputs if isinstance(path, str) and path]
    if not dem_paths:
        raise ValueError("resume validation-only requires DEM inputs from build_plan.json")

    plan = build_plan(
        backend=backend_spec,
        tiles=tiles,
        dem_paths=[str(p) for p in dem_paths],
        options=options,
        aoi=options.get("aoi"),
    )
    tile_statuses = [
        {"tile": tile, "status": "ok", "messages": ["resume validation-only"]} for tile in tiles
    ]
    report = build_report(
        backend=backend_spec,
        tile_statuses=tile_statuses,
        artifacts={"scenery_dir": str(output_dir), "resume_mode": "validate-only"},
        warnings=[],
        errors=[],
    )
    result = BuildResult(build_plan=plan, build_report=report)

    validation_options = dict(options)
    validation_options["validate_all"] = True

    with perf.span("xp12_checks"):
        if getattr(backend_spec, "supports_xp12_rasters", False):
            _apply_xp12_checks(report, validation_options, output_dir)
    with perf.span("autoortho_checks"):
        _apply_autoortho_checks(report, validation_options, output_dir)
    with perf.span("dds_validation"):
        _apply_dds_validation(report, validation_options, output_dir)
    with perf.span("dsf_validation"):
        _apply_dsf_validation(report, validation_options, output_dir)

    return _finalize_result(result, perf=perf, output_dir=output_dir, options=options)


def run_build(
    *,
    dem_paths: list[Path],
    tiles: list[str],
    backend_name: str,
    output_dir: Path,
    options: Mapping[str, Any],
) -> BuildResult:
    """Normalize DEM inputs, run the backend, and write plan/report JSON."""
    perf = PerfTracker(enabled=bool(options.get("profile")), track_memory=True)
    perf.start()
    backend = get_backend(backend_name)
    backend_spec = backend.spec()
    stack = None
    stack_path = options.get("dem_stack_path")
    if stack_path:
        stack = load_dem_stack(Path(stack_path))
        dem_paths = [layer.path for layer in stack.layers]
        options = {
            **options,
            "dem_stack": stack_to_options(stack),
        }
    requested_tiles = list(tiles)
    lock_inputs = {
        "dems": [str(path) for path in dem_paths],
        "dem_stack": stack_path,
        "tiles": requested_tiles,
        "aoi": options.get("aoi"),
        "aoi_crs": options.get("aoi_crs"),
    }
    lock_tools = {
        "runner": _resolve_tool_command(options.get("runner")),
        "dsftool": _resolve_tool_command(options.get("dsftool")),
        "ddstool": _resolve_tool_command(options.get("ddstool")),
    }
    lock_payload = build_config_lock(
        inputs=lock_inputs,
        options=options,
        tools={key: value for key, value in lock_tools.items() if value},
        output_dir=output_dir,
    )
    write_json(output_dir / "build_config.lock.json", lock_payload)

    resume_mode = options.get("resume")
    if resume_mode == "validate-only":
        return _resume_validation(
            dem_paths=dem_paths,
            tiles=requested_tiles,
            backend_spec=backend_spec,
            output_dir=output_dir,
            options=options,
            perf=perf,
        )
    resume_skip: set[str] = set()
    if resume_mode:
        resume_report = _load_json(output_dir / "build_report.json")
        if resume_report is None:
            raise ValueError("resume requires an existing build_report.json")
        resume_skip = _resume_ok_tiles(resume_report)

    _validate_build_inputs(tiles=requested_tiles, dem_paths=dem_paths, options=options)
    normalization_errors: dict[str, str] = {}
    guardrail_estimates: dict[str, Any] | None = None
    guardrail_warnings: list[str] = []
    coverage_min = options.get("coverage_min")
    tiles_for_backend = [tile for tile in requested_tiles if tile not in resume_skip]
    request = BuildRequest(
        tiles=tuple(tiles_for_backend),
        dem_paths=tuple(dem_paths),
        output_dir=output_dir,
        options=options,
    )

    result: BuildResult | None = None
    coverage_metrics: Mapping[str, Any] = {}
    try:
        if resume_skip and not tiles_for_backend:
            plan = build_plan(
                backend=backend_spec,
                tiles=requested_tiles,
                dem_paths=[str(p) for p in dem_paths],
                options=options,
                aoi=options.get("aoi"),
            )
            tile_statuses = [
                {
                    "tile": tile,
                    "status": "skipped",
                    "messages": ["resume: previously reported ok"],
                }
                for tile in requested_tiles
            ]
            report = build_report(
                backend=backend_spec,
                tile_statuses=tile_statuses,
                artifacts={
                    "scenery_dir": str(output_dir),
                    "resume_skipped": sorted(resume_skip),
                },
                warnings=[f"Resume skipped {len(resume_skip)} tile(s) with ok status."],
                errors=[],
            )
            result = BuildResult(build_plan=plan, build_report=report)
        elif options.get("dry_run"):
            plan = build_plan(
                backend=backend_spec,
                tiles=tiles,
                dem_paths=[str(p) for p in dem_paths],
                options=options,
                aoi=options.get("aoi"),
            )
            report = build_report(
                backend=backend_spec,
                tile_statuses=[
                    {"tile": tile, "status": "skipped", "messages": ["dry run"]} for tile in tiles
                ],
                artifacts={"scenery_dir": str(output_dir)},
                warnings=["Dry run enabled; no backend invoked."],
                errors=[],
            )
            result = BuildResult(build_plan=plan, build_report=report)
        else:
            if options.get("normalize", True):
                backend_profile = profile_for_backend(backend_name)
                target_crs = options.get("target_crs") or backend_spec.tile_dem_crs
                resolution = _resolution_from_options(options, tiles, target_crs)
                guardrail_estimates, guardrail_warnings = _estimate_build_guardrails(
                    tiles,
                    target_crs=target_crs,
                    resolution=resolution,
                    options=options,
                )
                fill_strategy = options.get("fill_strategy", "none")
                fill_value = float(options.get("fill_value", 0.0) or 0.0)
                fallback_dem_paths = [
                    Path(path) for path in options.get("fallback_dem_paths") or []
                ]
                tile_jobs_value = options.get("tile_jobs", 1)
                tile_jobs = int(1 if tile_jobs_value is None else tile_jobs_value)
                if tile_jobs < 0:
                    raise ValueError("tile_jobs must be >= 0")
                continue_on_error = bool(options.get("continue_on_error", False))
                coverage_metrics_enabled = bool(
                    options.get("coverage_metrics", True)
                    or coverage_min is not None
                    or (backend_profile and backend_profile.require_full_coverage)
                )
                mosaic_strategy = options.get("mosaic_strategy", "full")
                compression = _normalize_compression(options.get("normalized_compression"))
                cache_sha256 = bool(options.get("cache_sha256", False))
                cache_options = _normalization_cache_options(
                    target_crs=target_crs,
                    resampling=options.get("resampling", "bilinear"),
                    dst_nodata=options.get("dst_nodata"),
                    resolution=resolution,
                    fill_strategy=fill_strategy,
                    fill_value=fill_value,
                    backend_profile=backend_profile,
                    dem_stack=options.get("dem_stack"),
                    aoi=options.get("aoi"),
                    aoi_crs=options.get("aoi_crs"),
                    mosaic_strategy=mosaic_strategy,
                    normalized_compression=compression,
                )
                fallback_sources = fallback_dem_paths if fill_strategy == "fallback" else []
                normalization_cache = load_normalization_cache(output_dir / "normalized")
                cached_tile_paths: dict[str, str] = {}
                cached_tile_fingerprints: dict[str, SourceFingerprint] = {}
                cached_coverage: dict[str, CoverageMetrics] = {}
                pending_tiles = list(tiles)
                cache_compatible = (
                    normalization_cache is not None
                    and normalization_cache.matches_inputs(
                        sources=dem_paths,
                        fallback_sources=fallback_sources,
                        options=cache_options,
                        validate_hashes=cache_sha256,
                    )
                )
                if cache_compatible and normalization_cache is not None:
                    cached_tile_paths, pending_tiles = normalization_cache.resolve_tiles(
                        tiles,
                        validate_hashes=cache_sha256,
                    )
                    cached_tile_fingerprints = {
                        tile: normalization_cache.tile_fingerprints[tile]
                        for tile in cached_tile_paths
                        if tile in normalization_cache.tile_fingerprints
                    }
                    if coverage_metrics_enabled:
                        cached_coverage = {
                            tile: normalization_cache.coverage[tile]
                            for tile in cached_tile_paths
                            if tile in normalization_cache.coverage
                        }
                cached_tiles = [tile for tile in tiles if tile in cached_tile_paths]
                tiles_for_backend = tiles
                with perf.span("normalize"):
                    if cache_compatible and not pending_tiles and normalization_cache is not None:
                        coverage_metrics = cached_coverage if coverage_metrics_enabled else {}
                        options = {
                            **options,
                            "tile_dem_paths": dict(cached_tile_paths),
                        }
                        if normalization_cache.mosaic_valid(validate_hashes=cache_sha256):
                            options["mosaic_path"] = normalization_cache.mosaic_path
                    else:
                        target_tiles = pending_tiles if pending_tiles else tiles
                        if stack:
                            normalization = normalize_stack_for_tiles(
                                stack,
                                target_tiles,
                                output_dir / "normalized",
                                target_crs=target_crs,
                                resampling=options.get("resampling", "bilinear"),
                                dst_nodata=options.get("dst_nodata"),
                                resolution=resolution,
                                fill_strategy=fill_strategy,
                                fill_value=fill_value,
                                fallback_dem_paths=fallback_dem_paths,
                                backend_profile=backend_profile,
                                tile_jobs=tile_jobs,
                                continue_on_error=continue_on_error,
                                coverage_metrics=coverage_metrics_enabled,
                                mosaic_strategy=mosaic_strategy,
                                compression=compression,
                                aoi_path=Path(options["aoi"]) if options.get("aoi") else None,
                                aoi_crs=options.get("aoi_crs"),
                            )
                        else:
                            normalization = normalize_for_tiles(
                                dem_paths,
                                target_tiles,
                                output_dir / "normalized",
                                target_crs=target_crs,
                                resampling=options.get("resampling", "bilinear"),
                                dst_nodata=options.get("dst_nodata"),
                                resolution=resolution,
                                fill_strategy=fill_strategy,
                                fill_value=fill_value,
                                fallback_dem_paths=fallback_dem_paths,
                                backend_profile=backend_profile,
                                tile_jobs=tile_jobs,
                                continue_on_error=continue_on_error,
                                coverage_metrics=coverage_metrics_enabled,
                                mosaic_strategy=mosaic_strategy,
                                compression=compression,
                                aoi_path=Path(options["aoi"]) if options.get("aoi") else None,
                                aoi_crs=options.get("aoi_crs"),
                            )
                        normalization_errors = dict(normalization.errors)
                        if normalization_errors:
                            ok_tiles = [
                                tile for tile in target_tiles if tile not in normalization_errors
                            ]
                        else:
                            ok_tiles = target_tiles
                        tiles_for_backend = cached_tiles + ok_tiles
                        coverage_metrics = (
                            {**cached_coverage, **normalization.coverage}
                            if coverage_metrics_enabled
                            else {}
                        )
                        new_tile_paths = {
                            tile_result.tile: str(tile_result.path)
                            for tile_result in normalization.tile_results
                        }
                        merged_tile_paths = {**cached_tile_paths, **new_tile_paths}
                        options = {
                            **options,
                            "tile_dem_paths": merged_tile_paths,
                            "mosaic_path": str(normalization.mosaic_path),
                        }
                        if normalization_errors:
                            options = {
                                **options,
                                "normalization_errors": normalization_errors,
                            }
                        if not normalization_errors:
                            merged_fingerprints = {
                                **cached_tile_fingerprints,
                                **fingerprint_path_map(
                                    {tile: Path(path) for tile, path in new_tile_paths.items()},
                                    compute_sha256=cache_sha256,
                                ),
                            }
                            merged_coverage = {**cached_coverage, **normalization.coverage}
                            mosaic_path = Path(normalization.mosaic_path).resolve()
                            cache = NormalizationCache(
                                version=CACHE_VERSION,
                                sources=fingerprint_paths(dem_paths, compute_sha256=cache_sha256),
                                fallback_sources=fingerprint_paths(
                                    fallback_sources,
                                    compute_sha256=cache_sha256,
                                ),
                                options=dict(cache_options),
                                tiles=tuple(tiles),
                                tile_paths=merged_tile_paths,
                                tile_fingerprints=merged_fingerprints,
                                mosaic_path=str(mosaic_path),
                                mosaic_fingerprint=SourceFingerprint.from_path(
                                    mosaic_path,
                                    compute_sha256=cache_sha256,
                                )
                                if mosaic_path.exists()
                                else None,
                                coverage=merged_coverage,
                            )
                            write_normalization_cache(output_dir / "normalized", cache)
                request = BuildRequest(
                    tiles=tuple(tiles_for_backend),
                    dem_paths=tuple(dem_paths),
                    output_dir=output_dir,
                    options=options,
                )
                if normalization_errors and not tiles_for_backend:
                    plan = build_plan(
                        backend=backend_spec,
                        tiles=requested_tiles,
                        dem_paths=[str(p) for p in dem_paths],
                        options=options,
                        aoi=options.get("aoi"),
                    )
                    tile_statuses = [
                        {
                            "tile": tile,
                            "status": "error",
                            "messages": [f"Normalization failed: {normalization_errors[tile]}"],
                        }
                        for tile in requested_tiles
                    ]
                    report = build_report(
                        backend=backend_spec,
                        tile_statuses=tile_statuses,
                        artifacts={"scenery_dir": str(output_dir)},
                        warnings=[],
                        errors=[f"{tile}: normalization failed" for tile in requested_tiles],
                    )
                    result = BuildResult(build_plan=plan, build_report=report)
            if result is None:
                with perf.span("backend"):
                    result = backend.build(request)
                report = {
                    **result.build_report,
                    "tiles": [dict(tile) for tile in result.build_report.get("tiles", [])],
                    "warnings": list(result.build_report.get("warnings", [])),
                    "errors": list(result.build_report.get("errors", [])),
                }
                with perf.span("dem_sanity"):
                    _apply_dem_sanity_checks(report, dem_paths)
                with perf.span("triangle_guardrails"):
                    _apply_triangle_guardrails(report, options)
                if backend_spec.supports_xp12_rasters:
                    with perf.span("xp12_checks"):
                        _apply_xp12_checks(report, options, output_dir)
                    with perf.span("xp12_enrichment"):
                        _apply_xp12_enrichment(report, options, output_dir)
                with perf.span("autoortho_checks"):
                    _apply_autoortho_checks(report, options, output_dir)
                with perf.span("dds_validation"):
                    _apply_dds_validation(report, options, output_dir)
                with perf.span("dsf_validation"):
                    _apply_dsf_validation(report, options, output_dir)
                with perf.span("coverage_metrics"):
                    _apply_coverage_metrics(report, coverage_metrics)
                with perf.span("coverage_thresholds"):
                    _apply_coverage_thresholds(
                        report,
                        coverage_metrics,
                        min_coverage=coverage_min,
                        hard_fail=bool(options.get("coverage_hard_fail", False)),
                    )
                if normalization_errors:
                    for tile, error in normalization_errors.items():
                        report["tiles"].append(
                            {
                                "tile": tile,
                                "status": "error",
                                "messages": [f"Normalization failed: {error}"],
                            }
                        )
                        report.setdefault("errors", []).append(f"{tile}: normalization failed")
                if resume_skip:
                    for tile in sorted(resume_skip):
                        report["tiles"].append(
                            {
                                "tile": tile,
                                "status": "skipped",
                                "messages": ["resume: previously reported ok"],
                            }
                        )
                    report.setdefault("warnings", []).append(
                        f"Resume skipped {len(resume_skip)} tile(s) with ok status."
                    )
                    report.setdefault("artifacts", {})["resume_skipped"] = sorted(resume_skip)
                result = BuildResult(build_plan=result.build_plan, build_report=report)
        perf.stop()
    finally:
        perf.stop()

    if result is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Build did not produce a report.")

    report = dict(result.build_report)
    if guardrail_estimates:
        artifacts = dict(report.get("artifacts", {}))
        artifacts.setdefault("estimates", guardrail_estimates)
        report["artifacts"] = artifacts
    if guardrail_warnings:
        report.setdefault("warnings", []).extend(guardrail_warnings)
    report = _attach_performance(report, perf, output_dir, options)
    inputs = result.build_plan.get("inputs") if result.build_plan else None
    if inputs:
        report = {**report, "inputs": inputs}
    result = BuildResult(build_plan=result.build_plan, build_report=report)
    bundle_path = None
    if options.get("bundle_diagnostics"):
        bundle_path = default_bundle_path(output_dir)
        report_artifacts = dict(result.build_report.get("artifacts", {}))
        report_artifacts["diagnostics_bundle"] = str(bundle_path)
        report_with_bundle = {**result.build_report, "artifacts": report_artifacts}
        result = BuildResult(build_plan=result.build_plan, build_report=report_with_bundle)
    provenance, provenance_warnings = build_provenance(
        options=options,
        dem_paths=dem_paths,
        coverage_metrics=coverage_metrics,
    )
    plan = dict(result.build_plan)
    report = dict(result.build_report)
    plan["provenance"] = provenance
    report["provenance"] = provenance
    if provenance_warnings:
        report["warnings"] = list(report.get("warnings", [])) + provenance_warnings
    if options.get("stable_metadata"):
        plan.pop("created_at", None)
        report.pop("created_at", None)
    result = BuildResult(build_plan=plan, build_report=report)
    validate_build_plan(result.build_plan)
    validate_build_report(result.build_report)
    write_json(output_dir / "build_plan.json", result.build_plan)
    write_json(output_dir / "build_report.json", result.build_report)
    if bundle_path is not None:
        try:
            bundle_diagnostics(output_dir, output_path=bundle_path)
        except FileNotFoundError:
            pass
    return result
