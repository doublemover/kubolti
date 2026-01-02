"""CRS normalization and transformation helpers."""

from __future__ import annotations

from typing import Tuple

from pyproj import CRS, Transformer

Bounds = Tuple[float, float, float, float]


def normalize_crs(value: str | CRS) -> CRS:
    """Normalize CRS input into a pyproj CRS object."""
    return CRS.from_user_input(value)


def transformer(src: str | CRS, dst: str | CRS) -> Transformer:
    """Return a transformer that respects lon/lat axis order."""
    return Transformer.from_crs(normalize_crs(src), normalize_crs(dst), always_xy=True)


def _linspace(start: float, stop: float, count: int) -> list[float]:
    """Return evenly spaced values between start and stop inclusive."""
    if count <= 1:
        return [start]
    step = (stop - start) / (count - 1)
    return [start + step * index for index in range(count)]


def transform_bounds(
    bounds: Bounds,
    src: str | CRS,
    dst: str | CRS,
    *,
    densify_pts: int = 0,
) -> Bounds:
    """Transform bounding coordinates between CRSs."""
    minx, miny, maxx, maxy = bounds
    tx = transformer(src, dst)
    if densify_pts > 0:
        steps = densify_pts + 2
        xs: list[float] = []
        ys: list[float] = []
        for x in _linspace(minx, maxx, steps):
            xs.extend([x, x])
            ys.extend([miny, maxy])
        for y in _linspace(miny, maxy, steps):
            xs.extend([minx, maxx])
            ys.extend([y, y])
    else:
        xs = [minx, minx, maxx, maxx]
        ys = [miny, maxy, miny, maxy]
    out_xs, out_ys = tx.transform(xs, ys)
    return (min(out_xs), min(out_ys), max(out_xs), max(out_ys))
