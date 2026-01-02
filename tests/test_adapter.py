from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from dem2dsf.dem.adapter import (
    ORTHO4XP_PROFILE,
    BackendProfile,
    apply_backend_profile,
    profile_for_backend,
)
from tests.utils import write_raster


def test_apply_backend_profile_sets_nodata(tmp_path) -> None:
    src = tmp_path / "src.tif"
    dst = tmp_path / "dst.tif"
    write_raster(src, np.array([[1]], dtype=np.int16), bounds=(0.0, 0.0, 1.0, 1.0))

    apply_backend_profile(src, dst, ORTHO4XP_PROFILE)

    with rasterio.open(dst) as dataset:
        assert dataset.nodata == -32768.0


def test_apply_backend_profile_requires_crs(tmp_path) -> None:
    src = tmp_path / "src.tif"
    dst = tmp_path / "dst.tif"
    data = np.array([[1]], dtype=np.int16)
    with rasterio.open(
        src,
        "w",
        driver="GTiff",
        height=1,
        width=1,
        count=1,
        dtype=data.dtype,
        transform=from_bounds(0.0, 0.0, 1.0, 1.0, 1, 1),
    ) as dataset:
        dataset.write(data, 1)

    with pytest.raises(ValueError, match="declare a CRS"):
        apply_backend_profile(src, dst, ORTHO4XP_PROFILE)


def test_apply_backend_profile_requires_matching_crs(tmp_path) -> None:
    src = tmp_path / "src.tif"
    dst = tmp_path / "dst.tif"
    write_raster(
        src,
        np.array([[1]], dtype=np.int16),
        bounds=(0.0, 0.0, 1.0, 1.0),
        crs="EPSG:3857",
    )

    with pytest.raises(ValueError, match="CRS must match"):
        apply_backend_profile(src, dst, ORTHO4XP_PROFILE)


def test_apply_backend_profile_remaps_nodata(tmp_path) -> None:
    src = tmp_path / "src.tif"
    dst = tmp_path / "dst.tif"
    data = np.array([[1, -9999]], dtype=np.int16)
    write_raster(src, data, bounds=(0.0, 0.0, 1.0, 1.0), nodata=-9999)

    apply_backend_profile(src, dst, ORTHO4XP_PROFILE)

    with rasterio.open(dst) as dataset:
        assert dataset.nodata == -32768.0
        out = dataset.read(1)
        assert out[0, 1] == -32768.0


def test_apply_backend_profile_remaps_nan_nodata(tmp_path) -> None:
    src = tmp_path / "src.tif"
    dst = tmp_path / "dst.tif"
    data = np.array([[1.0, np.nan]], dtype=np.float32)
    write_raster(
        src,
        data,
        bounds=(0.0, 0.0, 1.0, 1.0),
        nodata=float("nan"),
    )

    apply_backend_profile(src, dst, ORTHO4XP_PROFILE)

    with rasterio.open(dst) as dataset:
        out = dataset.read(1)
        assert out[0, 1] == -32768.0


def test_apply_backend_profile_requires_full_coverage(tmp_path) -> None:
    src = tmp_path / "src.tif"
    dst = tmp_path / "dst.tif"
    data = np.array([[-9999]], dtype=np.int16)
    write_raster(src, data, bounds=(0.0, 0.0, 1.0, 1.0), nodata=-9999)

    with pytest.raises(ValueError, match="void-free"):
        apply_backend_profile(
            src,
            dst,
            BackendProfile(
                name="strict",
                crs="EPSG:4326",
                nodata=-9999.0,
                require_full_coverage=True,
            ),
        )


def test_apply_backend_profile_requires_full_coverage_nan(tmp_path) -> None:
    src = tmp_path / "src.tif"
    dst = tmp_path / "dst.tif"
    data = np.array([[np.nan]], dtype=np.float32)
    write_raster(
        src,
        data,
        bounds=(0.0, 0.0, 1.0, 1.0),
        nodata=float("nan"),
    )

    with pytest.raises(ValueError, match="void-free"):
        apply_backend_profile(
            src,
            dst,
            BackendProfile(
                name="strict-nan",
                crs="EPSG:4326",
                nodata=float("nan"),
                require_full_coverage=True,
            ),
        )


def test_profile_for_backend() -> None:
    assert profile_for_backend("ortho4xp") is ORTHO4XP_PROFILE
    assert profile_for_backend("missing") is None
