from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio

from dem2dsf.dem.adapter import ORTHO4XP_PROFILE
from dem2dsf.dem.pipeline import normalize_for_tiles, normalize_stack_for_tiles
from dem2dsf.dem.stack import DemLayer, DemStack
from tests.utils import write_raster


def test_normalize_for_tiles(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    data = np.array([[1, 2], [3, 4]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)

    result = normalize_for_tiles(
        [dem_path],
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
    )

    assert result.mosaic_path.exists()
    assert result.tile_results[0].path.exists()
    assert result.tile_results[0].tile == "+47+008"
    metrics = result.coverage["+47+008"]
    assert metrics.filled_pixels == 0
    assert metrics.coverage_before == 1.0
    assert metrics.coverage_after == 1.0


def test_normalize_for_tiles_parallel_jobs(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    data = np.array([[1, 2], [3, 4]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 49.0), nodata=-9999)

    result = normalize_for_tiles(
        [dem_path],
        ["+47+008", "+48+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        tile_jobs=2,
    )

    tiles = {tile.path.name for tile in result.tile_results}
    assert tiles == {"+47+008.tif", "+48+008.tif"}


def test_normalize_for_tiles_constant_fill(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    data = np.array([[1, -9999], [3, 4]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)

    result = normalize_for_tiles(
        [dem_path],
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        resampling="nearest",
        dst_nodata=-9999,
        fill_strategy="constant",
        fill_value=0.0,
    )

    tile_path = result.tile_results[0].path
    with rasterio.open(tile_path) as dataset:
        band = dataset.read(1)
    assert 0.0 in band
    metrics = result.coverage["+47+008"]
    assert metrics.filled_pixels == 1
    assert metrics.coverage_before < metrics.coverage_after


def test_normalize_for_tiles_fallback_fill(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    fallback_path = tmp_path / "fallback.tif"
    data = np.array([[1, -9999], [3, 4]], dtype=np.int16)
    fallback = np.array([[5, 6], [7, 8]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(fallback_path, fallback, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)

    result = normalize_for_tiles(
        [dem_path],
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        resampling="nearest",
        dst_nodata=-9999,
        fill_strategy="fallback",
        fallback_dem_paths=[fallback_path],
    )

    tile_path = result.tile_results[0].path
    with rasterio.open(tile_path) as dataset:
        band = dataset.read(1)
    assert 6 in band
    metrics = result.coverage["+47+008"]
    assert metrics.filled_pixels == 1


def test_normalize_for_tiles_applies_backend_profile(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    data = np.array([[1, -9999]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)

    result = normalize_for_tiles(
        [dem_path],
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        resampling="nearest",
        dst_nodata=-9999,
        backend_profile=ORTHO4XP_PROFILE,
    )

    tile_path = result.tile_results[0].path
    with rasterio.open(tile_path) as dataset:
        assert dataset.nodata == -32768.0


def test_normalize_for_tiles_resolution_override(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    data = np.array([[1, 2], [3, 4]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)

    result = normalize_for_tiles(
        [dem_path],
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        resampling="nearest",
        resolution=(0.5, 0.5),
    )

    tile_path = result.tile_results[0].path
    with rasterio.open(tile_path) as dataset:
        assert dataset.res[0] == pytest.approx(0.5)
        assert dataset.res[1] == pytest.approx(0.5)


def test_normalize_stack_for_tiles_aoi_priority(tmp_path) -> None:
    base_path = tmp_path / "base.tif"
    high_path = tmp_path / "high.tif"
    aoi_path = tmp_path / "aoi.json"
    data_base = np.array([[1, 1], [1, 1]], dtype=np.int16)
    data_high = np.array([[2, 2], [2, 2]], dtype=np.int16)
    write_raster(base_path, data_base, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(high_path, data_high, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    aoi_path.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [8.0, 47.0],
                        [8.5, 47.0],
                        [8.5, 48.0],
                        [8.0, 48.0],
                        [8.0, 47.0],
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    stack = DemStack(
        layers=(
            DemLayer(path=base_path, priority=0, aoi=None, nodata=-9999.0),
            DemLayer(path=high_path, priority=10, aoi=aoi_path, nodata=-9999.0),
        )
    )

    result = normalize_stack_for_tiles(
        stack,
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        resampling="nearest",
        dst_nodata=-9999.0,
        resolution=(0.5, 0.5),
    )

    tile_path = result.tile_results[0].path
    with rasterio.open(tile_path) as dataset:
        band = dataset.read(1)
    assert (band == 2).sum() > 0
    assert (band == 1).sum() > 0


def test_normalize_stack_for_tiles_aoi_requires_nodata(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    aoi_path = tmp_path / "aoi.json"
    data = np.array([[1, 1], [1, 1]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=None)
    aoi_path.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [8.0, 47.0],
                        [8.5, 47.0],
                        [8.5, 48.0],
                        [8.0, 48.0],
                        [8.0, 47.0],
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    stack = DemStack(
        layers=(
            DemLayer(path=dem_path, priority=0, aoi=aoi_path, nodata=None),
        )
    )

    with pytest.raises(ValueError, match="AOI mask requires a nodata value"):
        normalize_stack_for_tiles(
            stack,
            ["+47+008"],
            tmp_path / "work",
            target_crs="EPSG:4326",
            resampling="nearest",
        )
