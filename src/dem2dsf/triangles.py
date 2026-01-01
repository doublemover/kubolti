"""Triangle estimation helpers for DEM rasters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import rasterio


@dataclass(frozen=True)
class TriangleEstimate:
    """Estimated triangle counts for a raster grid."""

    count: int
    width: int
    height: int


def estimate_triangles_from_raster(path: Path) -> TriangleEstimate:
    """Estimate triangle counts based on raster dimensions."""
    with rasterio.open(path) as dataset:
        width = dataset.width
        height = dataset.height
    if width < 2 or height < 2:
        return TriangleEstimate(count=0, width=width, height=height)
    count = (width - 1) * (height - 1) * 2
    return TriangleEstimate(count=count, width=width, height=height)
