"""Data models used by DEM processing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

Bounds = Tuple[float, float, float, float]
Resolution = Tuple[float, float]


@dataclass(frozen=True)
class DemInfo:
    """Metadata extracted from a DEM file."""

    path: Path
    crs: str | None
    bounds: Bounds
    width: int
    height: int
    nodata: float | None
    resolution: Resolution
    dtype: str


@dataclass(frozen=True)
class MosaicResult:
    """Result of building a mosaic from multiple DEMs."""

    path: Path
    crs: str
    bounds: Bounds
    resolution: Resolution


@dataclass(frozen=True)
class WarpResult:
    """Result of warping a DEM to a target CRS."""

    path: Path
    crs: str
    bounds: Bounds
    resolution: Resolution


@dataclass(frozen=True)
class TileResult:
    """Result of writing a DEM tile."""

    tile: str
    path: Path
    bounds: Bounds
    resolution: Resolution
    nodata: float | None


@dataclass(frozen=True)
class CoverageMetrics:
    """Coverage statistics for nodata fill operations."""

    total_pixels: int
    nodata_pixels_before: int
    nodata_pixels_after: int
    coverage_before: float
    coverage_after: float
    filled_pixels: int
    strategy: str
    normalize_seconds: float = 0.0
