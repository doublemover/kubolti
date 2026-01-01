"""DEM inspection helpers."""

from __future__ import annotations

from pathlib import Path

import rasterio

from dem2dsf.dem.models import DemInfo


def inspect_dem(path: Path) -> DemInfo:
    """Collect metadata about a DEM on disk."""
    with rasterio.open(path) as dataset:
        crs = dataset.crs.to_string() if dataset.crs else None
        bounds = dataset.bounds
        return DemInfo(
            path=Path(path),
            crs=crs,
            bounds=(bounds.left, bounds.bottom, bounds.right, bounds.top),
            width=dataset.width,
            height=dataset.height,
            nodata=dataset.nodata,
            resolution=(abs(dataset.res[0]), abs(dataset.res[1])),
            dtype=dataset.dtypes[0],
        )
