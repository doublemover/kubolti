"""Warp helper for DEM reprojection."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

from dem2dsf.dem.crs import normalize_crs
from dem2dsf.dem.models import WarpResult

Resolution = Tuple[float, float]


def warp_dem(
    src_path: Path,
    output_path: Path,
    dst_crs: str,
    *,
    resolution: Optional[Resolution] = None,
    resampling: Resampling = Resampling.bilinear,
    dst_nodata: float | None = None,
    force_axis_order: bool = True,
) -> WarpResult:
    """Reproject a DEM to a target CRS and write a new GeoTIFF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dst_crs_obj = normalize_crs(dst_crs)
    env_options = {}
    if force_axis_order:
        env_options["OGR_CT_FORCE_TRADITIONAL_GIS_ORDER"] = "YES"

    with rasterio.Env(**env_options):
        with rasterio.open(src_path) as src:
            transform, width, height = calculate_default_transform(
                src.crs,
                dst_crs_obj,
                src.width,
                src.height,
                *src.bounds,
                resolution=resolution,
            )
            meta = src.meta.copy()
            meta.update(
                {
                    "crs": dst_crs_obj,
                    "transform": transform,
                    "width": width,
                    "height": height,
                    "nodata": dst_nodata if dst_nodata is not None else src.nodata,
                }
            )

            with rasterio.open(output_path, "w", **meta) as dest:
                for band in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band),
                        destination=rasterio.band(dest, band),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs_obj,
                        resampling=resampling,
                        src_nodata=src.nodata,
                        dst_nodata=meta["nodata"],
                    )

    with rasterio.open(output_path) as dataset:
        bounds = dataset.bounds
        return WarpResult(
            path=output_path,
            crs=dataset.crs.to_string(),
            bounds=(bounds.left, bounds.bottom, bounds.right, bounds.top),
            resolution=(abs(dataset.res[0]), abs(dataset.res[1])),
        )
