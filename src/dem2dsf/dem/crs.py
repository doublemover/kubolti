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


def transform_bounds(bounds: Bounds, src: str | CRS, dst: str | CRS) -> Bounds:
    """Transform bounding coordinates between CRSs."""
    minx, miny, maxx, maxy = bounds
    tx = transformer(src, dst)
    xs = [minx, minx, maxx, maxx]
    ys = [miny, maxy, miny, maxy]
    out_xs, out_ys = tx.transform(xs, ys)
    return (min(out_xs), min(out_ys), max(out_xs), max(out_ys))
