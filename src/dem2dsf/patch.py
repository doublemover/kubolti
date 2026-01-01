"""Patch workflow for localized DEM edits and rebuilds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask

from dem2dsf.build import run_build
from dem2dsf.dem.info import inspect_dem
from dem2dsf.dem.stack import load_aoi_shapes
from dem2dsf.dem.tiling import tile_bounds, write_tile_dem
from dem2dsf.dem.warp import warp_dem


@dataclass(frozen=True)
class PatchEntry:
    """Single patch entry describing a tile DEM override."""

    tile: str
    dem: Path
    aoi: Path | None
    nodata: float | None


@dataclass(frozen=True)
class PatchPlan:
    """Patch plan containing one or more entries."""

    schema_version: str
    entries: tuple[PatchEntry, ...]


def _nodata_mask(data: np.ndarray, nodata: float | None) -> np.ndarray:
    """Return a boolean mask where nodata values are present."""
    if nodata is None:
        return np.zeros(data.shape, dtype=bool)
    if np.isnan(nodata):
        return np.isnan(data)
    return data == nodata


def load_patch_plan(path: Path) -> PatchPlan:
    """Parse a patch plan from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Patch plan must be a JSON object.")
    raw_entries = data.get("patches")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("Patch plan requires a non-empty patches list.")
    entries: list[PatchEntry] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            raise ValueError("Patch entry must be an object.")
        tile = entry.get("tile")
        dem = entry.get("dem") or entry.get("path")
        if not tile or not dem:
            raise ValueError("Patch entry requires tile and dem fields.")
        tile_bounds(tile)
        nodata = entry.get("nodata")
        if nodata is not None:
            nodata = float(nodata)
        aoi = entry.get("aoi")
        entries.append(
            PatchEntry(
                tile=tile,
                dem=Path(dem),
                aoi=Path(aoi) if aoi else None,
                nodata=nodata,
            )
        )
    schema_version = str(data.get("schema_version", "1"))
    return PatchPlan(schema_version=schema_version, entries=tuple(entries))


def _apply_aoi_mask(tile_path: Path, shapes: list[dict[str, object]], nodata: float) -> None:
    """Apply an AOI mask to a patch tile."""
    with rasterio.open(tile_path, "r+") as dataset:
        data = dataset.read(1)
        mask = geometry_mask(
            shapes,
            out_shape=data.shape,
            transform=dataset.transform,
            invert=False,
        )
        if not mask.any():
            return
        data = data.copy()
        data[mask] = nodata
        dataset.write(data, 1)


def prepare_patch_tile(
    entry: PatchEntry,
    base_tile_path: Path,
    work_dir: Path,
    *,
    resampling: str = "bilinear",
) -> Path:
    """Warp and clip a patch DEM to the base tile grid."""
    work_dir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(base_tile_path) as base:
        base_crs = base.crs
        base_resolution = (abs(base.res[0]), abs(base.res[1]))
        base_nodata = base.nodata

    info = inspect_dem(entry.dem)
    if info.crs is None:
        raise ValueError(f"Patch DEM is missing CRS: {entry.dem}")

    patch_nodata = entry.nodata if entry.nodata is not None else base_nodata
    source_path = entry.dem
    if info.crs != base_crs.to_string():
        warped_path = work_dir / "warp" / entry.tile / entry.dem.name
        warp_dem(
            source_path,
            warped_path,
            base_crs.to_string(),
            resolution=base_resolution,
            resampling=Resampling[resampling],
            dst_nodata=patch_nodata,
        )
        source_path = warped_path

    tile_path = work_dir / "tiles" / entry.tile / f"{entry.tile}.tif"
    write_tile_dem(
        source_path,
        entry.tile,
        tile_path,
        resolution=base_resolution,
        resampling=Resampling[resampling],
        dst_nodata=patch_nodata,
    )

    if entry.aoi:
        if patch_nodata is None:
            raise ValueError("AOI mask requires a nodata value.")
        shapes = load_aoi_shapes(entry.aoi)
        _apply_aoi_mask(tile_path, shapes, patch_nodata)

    return tile_path


def apply_patch_to_tile(
    base_tile_path: Path,
    patch_tile_path: Path,
    output_path: Path,
) -> Path:
    """Combine a patch tile with a base tile on disk."""
    with rasterio.open(base_tile_path) as base:
        base_data = base.read(1)
        base_nodata = base.nodata
        meta = base.meta.copy()

    with rasterio.open(patch_tile_path) as patch:
        patch_data = patch.read(1)
        patch_nodata = patch.nodata if patch.nodata is not None else base_nodata

    mask = _nodata_mask(patch_data, patch_nodata)
    combined = np.where(mask, base_data, patch_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **meta) as dest:
        dest.write(combined, 1)
    return output_path


def _resolve_base_tile_path(
    build_dir: Path, options: dict[str, Any], tile: str
) -> Path:
    """Resolve the base tile DEM path from build metadata."""
    tile_dem_paths = options.get("tile_dem_paths") or {}
    candidate = tile_dem_paths.get(tile)
    if candidate:
        path = Path(candidate)
        if path.exists():
            return path
    normalized = build_dir / "normalized" / "tiles" / tile / f"{tile}.tif"
    if normalized.exists():
        return normalized
    raise FileNotFoundError(f"Base tile DEM not found for {tile}")


def run_patch(
    *,
    build_dir: Path,
    patch_plan_path: Path,
    output_dir: Path | None = None,
    options_override: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply a patch plan and run a partial rebuild."""
    plan_path = build_dir / "build_plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Missing build_plan.json in {build_dir}")
    base_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    backend_name = base_plan.get("backend", {}).get("name")
    if not backend_name:
        raise ValueError("Base build plan missing backend name.")
    options = dict(base_plan.get("options") or {})
    if options_override:
        options.update(options_override)
    options.setdefault("quality", "compat")

    patch_plan = load_patch_plan(patch_plan_path)
    tiles = [entry.tile for entry in patch_plan.entries]

    output_dir = output_dir or build_dir / "patches" / patch_plan_path.stem
    work_dir = output_dir / "patch_work"
    patched_tiles: dict[str, str] = {}
    resampling = options.get("resampling", "bilinear")

    for entry in patch_plan.entries:
        base_tile = _resolve_base_tile_path(build_dir, options, entry.tile)
        patch_tile = prepare_patch_tile(
            entry,
            base_tile,
            work_dir,
            resampling=resampling,
        )
        patched = output_dir / "normalized" / "tiles" / entry.tile / f"{entry.tile}.tif"
        apply_patch_to_tile(base_tile, patch_tile, patched)
        patched_tiles[entry.tile] = str(patched)

    options["tile_dem_paths"] = patched_tiles
    options["normalize"] = False
    options["dry_run"] = dry_run
    options["patch_plan_path"] = str(patch_plan_path)

    run_build(
        dem_paths=[Path(p) for p in base_plan.get("inputs", {}).get("dems", [])],
        tiles=tiles,
        backend_name=backend_name,
        output_dir=output_dir,
        options=options,
    )

    patch_report = {
        "schema_version": patch_plan.schema_version,
        "base_build_dir": str(build_dir),
        "patch_plan": str(patch_plan_path),
        "tiles": tiles,
        "patched_tile_paths": patched_tiles,
        "output_dir": str(output_dir),
    }
    report_path = output_dir / "patch_report.json"
    report_path.write_text(json.dumps(patch_report, indent=2), encoding="utf-8")
    return patch_report
