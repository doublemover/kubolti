"""Helpers for inferring tile lists from DEM or AOI bounds."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from dem2dsf.dem.aoi import bounds_from_shapes, load_aoi
from dem2dsf.dem.crs import transform_bounds
from dem2dsf.dem.info import inspect_dem
from dem2dsf.dem.tiling import tile_bounds, tiles_for_bounds

Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class TileInferenceResult:
    """Summary of inferred tiles and coverage estimates."""

    tiles: list[str]
    bounds: Bounds
    dem_bounds: Bounds | None
    aoi_bounds: Bounds | None
    coverage: dict[str, float]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _bounds_union(bounds_list: Iterable[Bounds]) -> Bounds:
    min_x = min(bounds[0] for bounds in bounds_list)
    min_y = min(bounds[1] for bounds in bounds_list)
    max_x = max(bounds[2] for bounds in bounds_list)
    max_y = max(bounds[3] for bounds in bounds_list)
    return (min_x, min_y, max_x, max_y)


def _bounds_intersection(left: Bounds, right: Bounds) -> Bounds | None:
    min_x = max(left[0], right[0])
    min_y = max(left[1], right[1])
    max_x = min(left[2], right[2])
    max_y = min(left[3], right[3])
    if min_x >= max_x or min_y >= max_y:
        return None
    return (min_x, min_y, max_x, max_y)


def _bounds_area(bounds: Bounds) -> float:
    return max(0.0, (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]))


def _bounds_to_wgs84(bounds: Bounds, crs: str) -> Bounds:
    if crs.upper() == "EPSG:4326":
        return bounds
    return transform_bounds(bounds, crs, "EPSG:4326", densify_pts=21)


def _infer_dem_bounds(dem_paths: Iterable[Path]) -> Bounds | None:
    bounds_list: list[Bounds] = []
    for path in dem_paths:
        info = inspect_dem(path)
        if info.crs is None:
            raise ValueError(f"DEM is missing CRS: {path}")
        bounds_list.append(_bounds_to_wgs84(info.bounds, info.crs))
    if not bounds_list:
        return None
    return _bounds_union(bounds_list)


def infer_tiles(
    dem_paths: Iterable[Path],
    *,
    aoi_path: Path | None = None,
    aoi_crs: str | None = None,
) -> TileInferenceResult:
    """Infer tile names from DEM and optional AOI bounds."""
    warnings: list[str] = []
    dem_bounds = _infer_dem_bounds(dem_paths)
    aoi_bounds = None

    if aoi_path:
        aoi = load_aoi(aoi_path, crs=aoi_crs)
        warnings.extend(aoi.warnings)
        aoi_bounds = _bounds_to_wgs84(bounds_from_shapes(aoi.shapes), aoi.crs)

    if dem_bounds is None and aoi_bounds is None:
        raise ValueError("Tile inference requires DEMs or an AOI polygon.")

    bounds = aoi_bounds or dem_bounds
    if bounds is None:
        raise ValueError("Tile inference bounds could not be determined.")

    coverage_bounds = bounds
    if dem_bounds and aoi_bounds:
        intersection = _bounds_intersection(dem_bounds, aoi_bounds)
        if intersection is None:
            warnings.append("AOI bounds do not overlap DEM bounds; coverage is zero.")
        coverage_bounds = intersection

    tiles = tiles_for_bounds(bounds)
    coverage: dict[str, float] = {}
    for tile in tiles:
        tile_extent = tile_bounds(tile)
        if coverage_bounds is None:
            coverage[tile] = 0.0
            continue
        overlap = _bounds_intersection(tile_extent, coverage_bounds)
        if overlap is None:
            coverage[tile] = 0.0
            continue
        coverage[tile] = _bounds_area(overlap) / _bounds_area(tile_extent)

    return TileInferenceResult(
        tiles=tiles,
        bounds=bounds,
        dem_bounds=dem_bounds,
        aoi_bounds=aoi_bounds,
        coverage=coverage,
        warnings=tuple(warnings),
    )
