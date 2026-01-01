"""DEM mosaic builder using rasterio merge."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import rasterio
from rasterio.merge import merge

from dem2dsf.dem.models import MosaicResult


def build_mosaic(
    dem_paths: Sequence[Path],
    output_path: Path,
    *,
    method: str = "first",
) -> MosaicResult:
    """Merge DEM inputs into a single GeoTIFF mosaic."""
    if not dem_paths:
        raise ValueError("At least one DEM path is required.")

    sources = [rasterio.open(path) for path in dem_paths]
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merge(
            sources,
            method=method,
            dst_path=output_path,
            dst_kwds={"driver": "GTiff"},
        )
    finally:
        for src in sources:
            src.close()

    with rasterio.open(output_path) as dataset:
        bounds = dataset.bounds
        return MosaicResult(
            path=output_path,
            crs=dataset.crs.to_string(),
            bounds=(bounds.left, bounds.bottom, bounds.right, bounds.top),
            resolution=(abs(dataset.res[0]), abs(dataset.res[1])),
        )
