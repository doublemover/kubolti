"""Tile naming and DEM tiling helpers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, Tuple

import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

from dem2dsf.dem.crs import transform_bounds as transform_bounds_xy
from dem2dsf.dem.models import TileResult

Bounds = Tuple[float, float, float, float]


def tile_bounds(tile: str) -> Bounds:
    """Return bounding coordinates for a +DD+DDD tile name."""
    if len(tile) != 7 or tile[0] not in "+-" or tile[3] not in "+-":
        raise ValueError(f"Invalid tile name: {tile}")
    lat = int(tile[0:3])
    lon = int(tile[3:7])
    min_lat = lat
    max_lat = lat + 1
    min_lon = lon
    max_lon = lon + 1
    return (min_lon, min_lat, max_lon, max_lat)


def tile_name(lat: int, lon: int) -> str:
    """Format a tile name from integer latitude/longitude."""
    return f"{lat:+03d}{lon:+04d}"


def tile_bounds_in_crs(tile: str, crs: rasterio.CRS) -> Bounds:
    """Return tile bounds transformed into the requested CRS."""
    bounds = tile_bounds(tile)
    if crs != rasterio.CRS.from_epsg(4326):
        return transform_bounds_xy(
            bounds,
            "EPSG:4326",
            crs.to_string(),
            densify_pts=21,
        )
    return bounds


def tiles_for_bounds(bounds: Bounds) -> list[str]:
    """Return all tile names intersecting the bounds."""
    min_lon, min_lat, max_lon, max_lat = bounds
    start_lat = math.floor(min_lat)
    end_lat = math.ceil(max_lat) - 1
    start_lon = math.floor(min_lon)
    end_lon = math.ceil(max_lon) - 1
    tiles = []
    for lat in range(start_lat, end_lat + 1):
        for lon in range(start_lon, end_lon + 1):
            tiles.append(tile_name(lat, lon))
    return tiles


def write_tile_dem(
    src_path: Path,
    tile: str,
    output_path: Path,
    *,
    resolution: Tuple[float, float] | None = None,
    resampling: Resampling = Resampling.bilinear,
    dst_nodata: float | None = None,
) -> TileResult:
    """Clip and resample a DEM into a single tile GeoTIFF."""
    bounds_wgs84 = tile_bounds(tile)
    with rasterio.open(src_path) as src:
        if src.crs is None:
            raise ValueError("Source DEM CRS is required for tiling.")
        bounds = tile_bounds_in_crs(tile, src.crs)
        min_x, min_y, max_x, max_y = bounds
        res = resolution or (abs(src.res[0]), abs(src.res[1]))
        width = max(1, int(math.ceil((max_x - min_x) / res[0])))
        height = max(1, int(math.ceil((max_y - min_y) / res[1])))
        transform = from_bounds(min_x, min_y, max_x, max_y, width, height)
        meta = src.meta.copy()
        nodata = dst_nodata if dst_nodata is not None else src.nodata
        meta.update(
            {
                "driver": "GTiff",
                "height": height,
                "width": width,
                "transform": transform,
                "crs": src.crs,
                "nodata": nodata,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **meta) as dest:
            for band in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band),
                    destination=rasterio.band(dest, band),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=src.crs,
                    resampling=resampling,
                    src_nodata=src.nodata,
                    dst_nodata=nodata,
                )
    return TileResult(
        tile=tile,
        path=output_path,
        bounds=bounds_wgs84,
        resolution=res,
        nodata=nodata,
    )


def iter_tile_paths(tile_root: Path, tiles: Iterable[str]) -> list[Path]:
    """Return expected tile paths beneath a root directory."""
    paths = []
    for tile in tiles:
        lat = tile[0:3]
        lon = tile[3:7]
        paths.append(tile_root / f"{lat}{lon}" / f"{tile}.tif")
    return paths
