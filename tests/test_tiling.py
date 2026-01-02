from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds

from dem2dsf.dem.tiling import (
    iter_tile_paths,
    tile_bounds,
    tile_bounds_in_crs,
    tile_name,
    tiles_for_bounds,
    write_tile_dem,
)
from tests.utils import write_raster


def test_tile_bounds_and_name() -> None:
    assert tile_name(47, 8) == "+47+008"
    assert tile_bounds("+47+008") == (8, 47, 9, 48)


def test_tile_bounds_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid tile name"):
        tile_bounds("bad")


def test_tiles_for_bounds() -> None:
    bounds = (8.2, 47.1, 9.0, 48.0)
    assert tiles_for_bounds(bounds) == ["+47+008"]


def test_write_tile_dem(tmp_path) -> None:
    src = tmp_path / "src.tif"
    write_raster(src, np.array([[5]], dtype=np.int16), bounds=(8.0, 47.0, 9.0, 48.0))

    out = tmp_path / "tile.tif"
    result = write_tile_dem(src, "+47+008", out)

    assert result.bounds == (8, 47, 9, 48)
    with rasterio.open(out) as dataset:
        data = dataset.read(1)
        assert data.shape == (1, 1)
        assert data[0, 0] == 5


def test_write_tile_dem_projected_bounds(tmp_path) -> None:
    src = tmp_path / "src.tif"
    bounds_wgs84 = (8.0, 47.0, 9.0, 48.0)
    bounds_3857 = transform_bounds(
        "EPSG:4326",
        "EPSG:3857",
        *bounds_wgs84,
        densify_pts=21,
    )
    data = np.array([[5, 6], [7, 8]], dtype=np.int16)
    write_raster(
        src,
        data,
        bounds=bounds_3857,
        crs="EPSG:3857",
        nodata=-9999,
    )

    out = tmp_path / "tile.tif"
    result = write_tile_dem(src, "+47+008", out)

    assert result.bounds == bounds_wgs84
    assert result.nodata == -9999
    with rasterio.open(out) as dataset:
        assert dataset.crs.to_epsg() == 3857
        out_bounds = dataset.bounds
    for actual, expected in zip(out_bounds, bounds_3857):
        assert actual == pytest.approx(expected, rel=1e-4, abs=1e-1)


def test_tile_bounds_in_crs_always_xy() -> None:
    bounds = tile_bounds("+47+008")
    crs = rasterio.CRS.from_epsg(25832)

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
    xs = []
    ys = []
    steps = 23
    for index in range(steps):
        t = index / (steps - 1)
        x = bounds[0] + (bounds[2] - bounds[0]) * t
        xs.extend([x, x])
        ys.extend([bounds[1], bounds[3]])
    for index in range(steps):
        t = index / (steps - 1)
        y = bounds[1] + (bounds[3] - bounds[1]) * t
        ys.extend([y, y])
        xs.extend([bounds[0], bounds[2]])

    out_xs, out_ys = transformer.transform(xs, ys)
    expected = (min(out_xs), min(out_ys), max(out_xs), max(out_ys))
    result = tile_bounds_in_crs("+47+008", crs)

    for actual, exp in zip(result, expected):
        assert actual == pytest.approx(exp, rel=1e-6, abs=1e-2)


def test_write_tile_dem_requires_crs(tmp_path) -> None:
    src = tmp_path / "src_no_crs.tif"
    data = np.array([[5]], dtype=np.int16)
    transform = from_bounds(8.0, 47.0, 9.0, 48.0, 1, 1)
    with rasterio.open(
        src,
        "w",
        driver="GTiff",
        height=1,
        width=1,
        count=1,
        dtype=data.dtype,
        transform=transform,
    ) as dataset:
        dataset.write(data, 1)

    with pytest.raises(ValueError, match="CRS is required"):
        write_tile_dem(src, "+47+008", tmp_path / "out.tif")


def test_iter_tile_paths() -> None:
    paths = iter_tile_paths(Path("root"), ["+47+008", "+48+009"])
    assert paths[0].as_posix().endswith("+47+008/+47+008.tif")
    assert paths[1].as_posix().endswith("+48+009/+48+009.tif")
