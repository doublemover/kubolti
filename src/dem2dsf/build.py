"""Build orchestration: normalization, backend execution, and validation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import rasterio

from dem2dsf.autoortho import scan_terrain_textures
from dem2dsf.backends.base import BuildRequest, BuildResult
from dem2dsf.backends.registry import get_backend
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
from dem2dsf.reporting import build_plan, build_report
from dem2dsf.tools.dsftool import roundtrip_dsf
from dem2dsf.triangles import estimate_triangles_from_raster
from dem2dsf.xp12 import enrich_dsf_rasters, find_global_dsf, inventory_dsf_rasters
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path
from dem2dsf.xplane_paths import parse_tile


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON payload to disk, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
        message = f"{tile}: coverage_before {metrics.coverage_before:.2%} below {min_coverage:.2%}"
        _ensure_messages(tile_entry).append(message)
        if hard_fail:
            _mark_error(tile_entry)
            report.setdefault("errors", []).append(message)
        else:
            _mark_warning(tile_entry)
            report.setdefault("warnings", []).append(message)


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
        if estimate.count > max_limit and not allow_overage:
            _mark_error(tile_entry)
            report.setdefault("errors", []).append(
                f"{tile}: triangle estimate {estimate.count} exceeds max {max_limit}"
            )
        elif estimate.count > warn_limit:
            _mark_warning(tile_entry)
            report.setdefault("warnings", []).append(
                f"{tile}: triangle estimate {estimate.count} exceeds warn {warn_limit}"
            )


def _apply_xp12_checks(
    report: dict[str, Any],
    options: Mapping[str, Any],
    output_dir: Path,
) -> None:
    """Inventory XP12 rasters in DSFs and record warnings/errors."""
    quality = options.get("quality", "compat")
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
            _ensure_messages(tile_entry).append("DSF output not found; XP12 raster check skipped.")
            _mark_warning(tile_entry)
            continue
        if not dsftool_cmd:
            message = "DSFTool not configured; XP12 raster check skipped."
            _ensure_messages(tile_entry).append(message)
            if quality == "xp12-enhanced":
                _mark_error(tile_entry)
                report.setdefault("errors", []).append(f"{tile}: {message}")
            else:
                _mark_warning(tile_entry)
                report.setdefault("warnings", []).append(f"{tile}: {message}")
            continue

        try:
            summary = inventory_dsf_rasters(
                dsftool_cmd,
                dsf_path,
                output_dir / "xp12" / tile,
                **dsftool_kwargs,
            )
        except RuntimeError as exc:
            _ensure_messages(tile_entry).append(str(exc))
            _mark_error(tile_entry)
            report.setdefault("errors", []).append(f"{tile}: {exc}")
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
            _ensure_messages(tile_entry).append(message)
            if quality == "xp12-enhanced":
                _mark_error(tile_entry)
                report.setdefault("errors", []).append(f"{tile}: {message}")
            else:
                _mark_warning(tile_entry)
                report.setdefault("warnings", []).append(f"{tile}: {message}")
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
            _ensure_messages(tile_entry).append(message)
            _mark_error(tile_entry)
        report.setdefault("errors", []).append(message)
        return

    for tile_entry in report.get("tiles", []):
        tile = tile_entry.get("tile")
        if not tile:
            continue
        dsf_path = xplane_dsf_path(output_dir, tile)
        if not dsf_path.exists():
            _ensure_messages(tile_entry).append("DSF output not found; XP12 enrichment skipped.")
            _mark_warning(tile_entry)
            continue
        global_dsf = find_global_dsf(global_root, tile)
        if not global_dsf:
            _ensure_messages(tile_entry).append(
                "Global scenery DSF not found; XP12 enrichment skipped."
            )
            _mark_warning(tile_entry)
            report.setdefault("warnings", []).append(f"{tile}: global scenery DSF not found")
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
            _ensure_messages(tile_entry).append(f"XP12 enrichment failed: {result.error}")
            _mark_error(tile_entry)
            report.setdefault("errors", []).append(f"{tile}: XP12 enrichment failed")
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
                _ensure_messages(tile_entry).append(str(exc))
                _mark_warning(tile_entry)
                report.setdefault("warnings", []).append(f"{tile}: xp12 post-check failed")


def _apply_autoortho_checks(
    report: dict[str, Any],
    options: Mapping[str, Any],
    output_dir: Path,
) -> None:
    """Scan terrain textures for AutoOrtho compatibility issues."""
    if not options.get("autoortho"):
        return

    textures = scan_terrain_textures(output_dir)
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
            _mark_warning(tile_entry)
    if textures.invalid:
        report.setdefault("warnings", []).append(
            f"AutoOrtho invalid texture refs: {', '.join(textures.invalid[:5])}"
        )
    if textures.missing:
        report.setdefault("warnings", []).append(
            f"AutoOrtho missing texture refs: {', '.join(textures.missing[:5])}"
        )


def _apply_dsf_validation(
    report: dict[str, Any],
    options: Mapping[str, Any],
    output_dir: Path,
) -> None:
    """Validate DSF structure and geographic bounds."""
    dsftool_cmd = _resolve_tool_command(options.get("dsftool"))
    dsftool_kwargs = _dsftool_kwargs(options)
    if not dsftool_cmd:
        message = "DSFTool not configured; DSF validation skipped."
        for tile_entry in report.get("tiles", []):
            _ensure_messages(tile_entry).append(message)
            _mark_warning(tile_entry)
        report.setdefault("warnings", []).append(message)
        return

    for tile_entry in report.get("tiles", []):
        tile = tile_entry.get("tile")
        if not tile:
            continue
        dsf_path = xplane_dsf_path(output_dir, tile)
        if not dsf_path.exists():
            _ensure_messages(tile_entry).append("DSF output not found; DSF validation skipped.")
            _mark_warning(tile_entry)
            continue
        work_dir = output_dir / "dsf_validation" / tile
        work_dir.mkdir(parents=True, exist_ok=True)
        text_path = work_dir / f"{dsf_path.stem}.txt"
        rebuilt_path = work_dir / dsf_path.name
        metrics = _ensure_metrics(tile_entry)
        validation_metrics: dict[str, object] = {
            "roundtrip": "pending",
            "text_path": str(text_path),
            "rebuilt_path": str(rebuilt_path),
        }
        metrics["dsf_validation"] = validation_metrics
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
            _ensure_messages(tile_entry).append(message)
            _mark_error(tile_entry)
            report.setdefault("errors", []).append(f"{tile}: {message}")
            continue
        validation_metrics["roundtrip"] = "ok"
        try:
            properties = parse_properties_from_file(text_path)
            actual_bounds = parse_bounds(properties)
        except ValueError as exc:
            message = f"DSF bounds parse failed: {exc}"
            validation_metrics["bounds_error"] = str(exc)
            _ensure_messages(tile_entry).append(message)
            _mark_error(tile_entry)
            report.setdefault("errors", []).append(f"{tile}: {message}")
            continue
        expected_bounds = expected_bounds_for_tile(tile)
        mismatches = compare_bounds(expected_bounds, actual_bounds)
        validation_metrics["bounds"] = {
            "expected": expected_bounds.__dict__,
            "actual": actual_bounds.__dict__,
            "mismatches": mismatches,
        }
        if mismatches:
            message = f"DSF bounds mismatch: {', '.join(mismatches)}"
            _ensure_messages(tile_entry).append(message)
            _mark_error(tile_entry)
            report.setdefault("errors", []).append(f"{tile}: {message}")


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
    _validate_build_inputs(tiles=tiles, dem_paths=dem_paths, options=options)
    requested_tiles = list(tiles)
    normalization_errors: dict[str, str] = {}
    guardrail_estimates: dict[str, Any] | None = None
    guardrail_warnings: list[str] = []
    coverage_min = options.get("coverage_min")
    tiles_for_backend = tiles
    request = BuildRequest(
        tiles=tuple(tiles),
        dem_paths=tuple(dem_paths),
        output_dir=output_dir,
        options=options,
    )

    result: BuildResult | None = None
    coverage_metrics: Mapping[str, Any] = {}
    try:
        if options.get("dry_run"):
            plan = build_plan(
                backend=backend_spec,
                tiles=tiles,
                dem_paths=[str(p) for p in dem_paths],
                options=options,
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
                with perf.span("triangle_guardrails"):
                    _apply_triangle_guardrails(report, options)
                if backend_spec.supports_xp12_rasters:
                    with perf.span("xp12_checks"):
                        _apply_xp12_checks(report, options, output_dir)
                    with perf.span("xp12_enrichment"):
                        _apply_xp12_enrichment(report, options, output_dir)
                with perf.span("autoortho_checks"):
                    _apply_autoortho_checks(report, options, output_dir)
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
