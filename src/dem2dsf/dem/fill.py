"""Raster fill strategies for nodata gaps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import rasterio
from rasterio.fill import fillnodata


def _nodata_mask(data: np.ndarray, nodata: float | None) -> np.ndarray:
    """Return a boolean mask where nodata values are present."""
    if nodata is None:
        return np.zeros(data.shape, dtype=bool)
    if np.isnan(nodata):
        return np.isnan(data)
    return data == nodata


@dataclass(frozen=True)
class FillResult:
    """Result of a fill operation on a raster band."""

    filled: np.ndarray
    nodata: float | None
    filled_pixels: int
    nodata_pixels_after: int


def fill_with_constant(
    data: np.ndarray,
    *,
    nodata: float | None,
    fill_value: float,
) -> FillResult:
    """Fill nodata pixels with a constant value."""
    if nodata is None:
        return FillResult(data, nodata, 0, 0)
    mask = _nodata_mask(data, nodata)
    filled = data.copy()
    filled[mask] = fill_value
    after_mask = _nodata_mask(filled, nodata)
    filled_pixels = int(mask.sum() - after_mask.sum())
    return FillResult(filled, nodata, filled_pixels, int(after_mask.sum()))


def fill_with_interpolation(
    data: np.ndarray,
    *,
    nodata: float | None,
    max_search_distance: int = 100,
) -> FillResult:
    """Fill nodata pixels by interpolating neighboring values."""
    if nodata is None:
        return FillResult(data, nodata, 0, 0)
    mask = _nodata_mask(data, nodata)
    if not mask.any():
        return FillResult(data, nodata, 0, 0)
    filled = fillnodata(data, mask=~mask, max_search_distance=max_search_distance)
    after_mask = _nodata_mask(filled, nodata)
    filled_pixels = int(mask.sum() - after_mask.sum())
    return FillResult(filled, nodata, filled_pixels, int(after_mask.sum()))


def fill_with_fallback(
    primary: np.ndarray,
    fallback: np.ndarray,
    *,
    nodata: float | None,
) -> FillResult:
    """Fill nodata pixels from a fallback raster of the same shape."""
    if nodata is None:
        return FillResult(primary, nodata, 0, 0)
    if primary.shape != fallback.shape:
        raise ValueError("Primary and fallback rasters must share a shape.")
    mask = _nodata_mask(primary, nodata)
    merged = primary.copy()
    merged[mask] = fallback[mask]
    after_mask = _nodata_mask(merged, nodata)
    filled_pixels = int(mask.sum() - after_mask.sum())
    return FillResult(merged, nodata, filled_pixels, int(after_mask.sum()))


def fill_tile_in_place(
    path: str,
    *,
    strategy: str,
    nodata: Optional[float],
    fill_value: float = 0.0,
) -> int:
    """Apply a fill strategy directly to a raster file on disk."""
    with rasterio.open(path, "r+") as dataset:
        band = dataset.read(1)
        nodata_value = nodata if nodata is not None else dataset.nodata
        if strategy == "constant":
            result = fill_with_constant(band, nodata=nodata_value, fill_value=fill_value)
        elif strategy == "interpolate":
            result = fill_with_interpolation(band, nodata=nodata_value)
        else:
            raise ValueError(f"Unknown fill strategy: {strategy}")
        dataset.write(result.filled, 1)
        return result.filled_pixels
