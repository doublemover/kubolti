"""DEM inspection helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from dem2dsf.dem.models import DemInfo


def _read_vertical_units(dataset: Any) -> str | None:
    units = None
    try:
        units_list = dataset.units
        if units_list:
            units = units_list[0]
    except AttributeError:
        units = None
    if not units:
        tags = dataset.tags()
        for key in ("units", "unit", "vertical_units"):
            value = tags.get(key)
            if value:
                units = value
                break
    return units


def _sample_stats(
    dataset: Any,
) -> tuple[float | None, float | None, float | None, float | None]:
    max_dim = 512
    scale = min(1.0, max_dim / max(dataset.width, dataset.height))
    height = max(1, int(dataset.height * scale))
    width = max(1, int(dataset.width * scale))
    data = dataset.read(1, out_shape=(height, width), masked=True)
    mask = np.ma.getmaskarray(data)
    nodata_ratio = float(mask.sum() / data.size) if data.size else None
    nan_ratio = None
    if np.issubdtype(data.dtype, np.floating):
        nan_mask = np.isnan(np.ma.getdata(data))
        nan_ratio = float(nan_mask.sum() / data.size) if data.size else None
        if nan_mask.any():
            data = np.ma.array(np.ma.getdata(data), mask=mask | nan_mask)
    min_val = float(data.min()) if data.count() else None
    max_val = float(data.max()) if data.count() else None
    return min_val, max_val, nan_ratio, nodata_ratio


def inspect_dem(path: Path, *, sample: bool = False) -> DemInfo:
    """Collect metadata about a DEM on disk."""
    with rasterio.open(path) as dataset:
        crs = dataset.crs.to_string() if dataset.crs else None
        bounds = dataset.bounds
        min_val = max_val = nan_ratio = nodata_ratio = None
        if sample:
            min_val, max_val, nan_ratio, nodata_ratio = _sample_stats(dataset)
        return DemInfo(
            path=Path(path),
            crs=crs,
            bounds=(bounds.left, bounds.bottom, bounds.right, bounds.top),
            width=dataset.width,
            height=dataset.height,
            nodata=dataset.nodata,
            resolution=(abs(dataset.res[0]), abs(dataset.res[1])),
            dtype=dataset.dtypes[0],
            vertical_units=_read_vertical_units(dataset),
            min_elevation=min_val,
            max_elevation=max_val,
            nan_ratio=nan_ratio,
            nodata_ratio=nodata_ratio,
        )
