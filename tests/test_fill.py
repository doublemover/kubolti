from __future__ import annotations

import numpy as np

from dem2dsf.dem.fill import (
    fill_tile_in_place,
    fill_with_constant,
    fill_with_fallback,
    fill_with_interpolation,
)


def test_fill_with_constant() -> None:
    data = np.array([[1.0, -9999.0], [3.0, -9999.0]], dtype=np.float32)
    result = fill_with_constant(data, nodata=-9999.0, fill_value=0.0)
    assert result.filled_pixels == 2
    assert result.filled[0, 1] == 0.0


def test_fill_with_constant_no_nodata() -> None:
    data = np.array([[1.0, 2.0]], dtype=np.float32)
    result = fill_with_constant(data, nodata=None, fill_value=0.0)
    assert result.filled_pixels == 0


def test_fill_with_constant_nan_nodata() -> None:
    data = np.array([[1.0, np.nan], [np.nan, 2.0]], dtype=np.float32)
    result = fill_with_constant(data, nodata=np.nan, fill_value=0.0)
    assert result.filled_pixels == 2
    assert np.isnan(result.filled).sum() == 0


def test_fill_with_interpolation() -> None:
    data = np.array([[1.0, -9999.0], [3.0, 4.0]], dtype=np.float32)
    result = fill_with_interpolation(data, nodata=-9999.0, max_search_distance=2)
    assert result.filled_pixels == 1
    assert result.filled[0, 1] != -9999.0


def test_fill_with_interpolation_no_mask() -> None:
    data = np.array([[1.0, 2.0]], dtype=np.float32)
    result = fill_with_interpolation(data, nodata=-9999.0)
    assert result.filled_pixels == 0


def test_fill_with_interpolation_no_nodata() -> None:
    data = np.array([[1.0, 2.0]], dtype=np.float32)
    result = fill_with_interpolation(data, nodata=None)
    assert result.filled_pixels == 0


def test_fill_with_interpolation_nan_nodata() -> None:
    data = np.array([[1.0, np.nan], [3.0, 4.0]], dtype=np.float32)
    result = fill_with_interpolation(data, nodata=np.nan, max_search_distance=2)
    assert result.filled_pixels == 1
    assert not np.isnan(result.filled[0, 1])


def test_fill_with_fallback() -> None:
    primary = np.array([[1.0, -9999.0]], dtype=np.float32)
    fallback = np.array([[2.0, 3.0]], dtype=np.float32)
    result = fill_with_fallback(primary, fallback, nodata=-9999.0)
    assert result.filled_pixels == 1
    assert result.filled[0, 1] == 3.0


def test_fill_with_fallback_no_nodata() -> None:
    primary = np.array([[1.0, 2.0]], dtype=np.float32)
    fallback = np.array([[3.0, 4.0]], dtype=np.float32)
    result = fill_with_fallback(primary, fallback, nodata=None)
    assert result.filled_pixels == 0


def test_fill_with_fallback_nan_nodata() -> None:
    primary = np.array([[1.0, np.nan]], dtype=np.float32)
    fallback = np.array([[2.0, 3.0]], dtype=np.float32)
    result = fill_with_fallback(primary, fallback, nodata=np.nan)
    assert result.filled_pixels == 1
    assert result.filled[0, 1] == 3.0


def test_fill_with_fallback_mismatch() -> None:
    primary = np.array([[1.0]], dtype=np.float32)
    fallback = np.array([[2.0, 3.0]], dtype=np.float32)
    try:
        fill_with_fallback(primary, fallback, nodata=-9999.0)
    except ValueError as exc:
        assert "share a shape" in str(exc)
    else:
        raise AssertionError("Expected shape mismatch error")


def test_fill_tile_in_place(tmp_path) -> None:
    path = tmp_path / "tile.tif"
    data = np.array([[1.0, -9999.0]], dtype=np.float32)
    import rasterio
    from rasterio.transform import from_bounds

    transform = from_bounds(0.0, 0.0, 1.0, 1.0, 2, 1)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=1,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dataset:
        dataset.write(data, 1)

    filled = fill_tile_in_place(str(path), strategy="constant", nodata=None, fill_value=5.0)
    assert filled == 1

    filled = fill_tile_in_place(str(path), strategy="interpolate", nodata=-9999.0)
    assert filled >= 0

    try:
        fill_tile_in_place(str(path), strategy="bogus", nodata=-9999.0)
    except ValueError as exc:
        assert "Unknown fill strategy" in str(exc)
    else:
        raise AssertionError("Expected invalid strategy error")
