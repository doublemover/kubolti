from __future__ import annotations

from dem2dsf.dem.crs import transform_bounds


def test_transform_bounds_axis_order() -> None:
    bounds = (2.0, 1.0, 2.5, 1.5)
    result = transform_bounds(bounds, "EPSG:4326", "EPSG:3857")

    minx, miny, maxx, maxy = result
    assert minx < maxx
    assert miny < maxy
    assert 200000 < minx < 300000
    assert 100000 < miny < 200000
