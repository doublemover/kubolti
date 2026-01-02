from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from dem2dsf.dem import pipeline
from dem2dsf.dem.adapter import ORTHO4XP_PROFILE
from dem2dsf.dem.stack import DemLayer, DemStack
from tests.utils import write_raster


def test_nodata_mask_handles_none_and_nan() -> None:
    data = np.array([[1.0, np.nan]])
    assert not pipeline._nodata_mask(data, None).any()
    mask = pipeline._nodata_mask(data, float("nan"))
    assert mask[0, 1]


def test_apply_aoi_mask_noop(tmp_path: Path) -> None:
    tile_path = tmp_path / "tile.tif"
    write_raster(
        tile_path,
        np.array([[1]], dtype=np.int16),
        bounds=(0.0, 0.0, 1.0, 1.0),
        nodata=-9999,
    )
    shapes = [
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [0.0, 0.0],
                    [1.0, 0.0],
                    [1.0, 1.0],
                    [0.0, 1.0],
                    [0.0, 0.0],
                ]
            ],
        }
    ]

    pipeline._apply_aoi_mask(tile_path, shapes, -9999.0)

    with rasterio.open(tile_path) as dataset:
        assert dataset.read(1)[0, 0] == 1


def test_combine_stack_tiles_requires_layers() -> None:
    with pytest.raises(ValueError, match="No stack layers"):
        pipeline._combine_stack_tiles([], None)


def test_apply_fill_strategy_interpolate(tmp_path: Path) -> None:
    tile_path = tmp_path / "tile.tif"
    data = np.array([[1, -9999], [3, 4]], dtype=np.int16)
    write_raster(
        tile_path,
        data,
        bounds=(0.0, 0.0, 1.0, 1.0),
        nodata=-9999,
    )

    filled = pipeline._apply_fill_strategy(
        tile_path,
        strategy="interpolate",
        nodata=-9999,
        fill_value=0.0,
        fallback_path=None,
    )

    assert filled is not None
    assert filled.filled_pixels >= 0


def test_apply_fill_strategy_requires_fallback(tmp_path: Path) -> None:
    tile_path = tmp_path / "tile.tif"
    write_raster(
        tile_path,
        np.array([[1, -9999]], dtype=np.int16),
        bounds=(0.0, 0.0, 1.0, 1.0),
        nodata=-9999,
    )

    with pytest.raises(ValueError, match="Fallback fill requires fallback DEMs"):
        pipeline._apply_fill_strategy(
            tile_path,
            strategy="fallback",
            nodata=-9999,
            fill_value=0.0,
            fallback_path=None,
        )


def test_apply_fill_strategy_unknown(tmp_path: Path) -> None:
    tile_path = tmp_path / "tile.tif"
    write_raster(
        tile_path,
        np.array([[1]], dtype=np.int16),
        bounds=(0.0, 0.0, 1.0, 1.0),
    )

    with pytest.raises(ValueError, match="Unknown fill strategy"):
        pipeline._apply_fill_strategy(
            tile_path,
            strategy="mystery",
            nodata=None,
            fill_value=0.0,
            fallback_path=None,
        )


def test_prepare_sources_requires_crs(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    data = np.array([[1]], dtype=np.int16)
    transform = from_bounds(0.0, 0.0, 1.0, 1.0, 1, 1)
    with rasterio.open(
        dem_path,
        "w",
        driver="GTiff",
        height=1,
        width=1,
        count=1,
        dtype=data.dtype,
        transform=transform,
    ) as dataset:
        dataset.write(data, 1)

    with pytest.raises(ValueError, match="missing CRS"):
        pipeline._prepare_sources(
            [dem_path],
            work_dir=tmp_path,
            target_crs="EPSG:4326",
            resampling="nearest",
            resolution=None,
            dst_nodata=None,
            label="primary",
        )


def test_prepare_sources_warp(monkeypatch, tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        np.array([[1]], dtype=np.int16),
        bounds=(0.0, 0.0, 1.0, 1.0),
        crs="EPSG:3857",
    )

    calls = {}

    def fake_warp(src_path, dst_path, target_crs, resolution, resampling, dst_nodata):
        calls["target_crs"] = target_crs
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(pipeline, "warp_dem", fake_warp)

    result = pipeline._prepare_sources(
        [dem_path],
        work_dir=tmp_path,
        target_crs="EPSG:4326",
        resampling="nearest",
        resolution=None,
        dst_nodata=None,
        label="primary",
    )

    assert result[0].exists()
    assert calls["target_crs"] == "EPSG:4326"


def test_normalize_for_tiles_requires_dem() -> None:
    with pytest.raises(ValueError, match="At least one DEM path is required"):
        pipeline.normalize_for_tiles(
            [],
            ["+47+008"],
            Path("work"),
            target_crs="EPSG:4326",
        )


def test_normalize_for_tiles_multiple_dem_mosaic(tmp_path: Path) -> None:
    dem_a = tmp_path / "a.tif"
    dem_b = tmp_path / "b.tif"
    data = np.array([[1]], dtype=np.int16)
    write_raster(dem_a, data, bounds=(8.0, 47.0, 9.0, 48.0))
    write_raster(dem_b, data, bounds=(8.0, 47.0, 9.0, 48.0))

    result = pipeline.normalize_for_tiles(
        [dem_a, dem_b],
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
    )

    assert result.mosaic_path.name == "mosaic.tif"
    assert result.mosaic_path.exists()


def test_normalize_for_tiles_vrt_mosaic(tmp_path: Path) -> None:
    with rasterio.Env() as env:
        drivers = env.drivers()
    if "VRT" not in drivers:
        pytest.skip("VRT driver not available")
    dem_a = tmp_path / "a.tif"
    dem_b = tmp_path / "b.tif"
    data = np.array([[1]], dtype=np.int16)
    write_raster(dem_a, data, bounds=(8.0, 47.0, 9.0, 48.0))
    write_raster(dem_b, data, bounds=(8.0, 47.0, 9.0, 48.0))

    result = pipeline.normalize_for_tiles(
        [dem_a, dem_b],
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        mosaic_strategy="vrt",
    )

    assert result.mosaic_path.name == "mosaic.vrt"
    assert result.mosaic_path.exists()


def test_normalize_for_tiles_fallback_requires_paths(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
    )

    with pytest.raises(ValueError, match="Fallback fill requires fallback DEMs"):
        pipeline.normalize_for_tiles(
            [dem_path],
            ["+47+008"],
            tmp_path / "work",
            target_crs="EPSG:4326",
            fill_strategy="fallback",
        )


def test_normalize_for_tiles_fallback_mosaic(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    fallback_a = tmp_path / "fallback_a.tif"
    fallback_b = tmp_path / "fallback_b.tif"
    data = np.array([[1, -9999], [3, 4]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(fallback_a, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(fallback_b, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)

    result = pipeline.normalize_for_tiles(
        [dem_path],
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        fill_strategy="fallback",
        fallback_dem_paths=[fallback_a, fallback_b],
    )

    assert result.mosaic_path.exists()


def test_normalize_stack_for_tiles_requires_layers(tmp_path: Path) -> None:
    stack = DemStack(layers=())
    with pytest.raises(ValueError, match="at least one layer"):
        pipeline.normalize_stack_for_tiles(
            stack,
            ["+47+008"],
            tmp_path / "work",
            target_crs="EPSG:4326",
        )


def test_normalize_stack_for_tiles_backend_profile(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    stack = DemStack(layers=(DemLayer(path=dem_path, priority=0, aoi=None, nodata=-9999.0),))

    result = pipeline.normalize_stack_for_tiles(
        stack,
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        backend_profile=ORTHO4XP_PROFILE,
    )

    with rasterio.open(result.tile_results[0].path) as dataset:
        assert dataset.nodata == ORTHO4XP_PROFILE.nodata


def test_normalize_stack_for_tiles_fallback_mosaic(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    fallback_a = tmp_path / "fallback_a.tif"
    fallback_b = tmp_path / "fallback_b.tif"
    data = np.array([[1, -9999], [3, 4]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(fallback_a, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(fallback_b, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)

    stack = DemStack(layers=(DemLayer(path=dem_path, priority=0, aoi=None, nodata=-9999.0),))

    result = pipeline.normalize_stack_for_tiles(
        stack,
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        fill_strategy="fallback",
        fallback_dem_paths=[fallback_a, fallback_b],
    )

    assert result.mosaic_path.exists()


def test_normalize_stack_for_tiles_fallback_requires_paths(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    stack = DemStack(layers=(DemLayer(path=dem_path, priority=0, aoi=None, nodata=-9999.0),))

    with pytest.raises(ValueError, match="Fallback fill requires fallback DEMs"):
        pipeline.normalize_stack_for_tiles(
            stack,
            ["+47+008"],
            tmp_path / "work",
            target_crs="EPSG:4326",
            fill_strategy="fallback",
        )


def test_normalize_stack_for_tiles_single_fallback(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    fallback = tmp_path / "fallback.tif"
    data = np.array([[1, -9999], [3, 4]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(fallback, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    stack = DemStack(layers=(DemLayer(path=dem_path, priority=0, aoi=None, nodata=-9999.0),))

    result = pipeline.normalize_stack_for_tiles(
        stack,
        ["+47+008"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        fill_strategy="fallback",
        fallback_dem_paths=[fallback],
    )

    assert result.mosaic_path.exists()


def test_normalize_stack_for_tiles_no_tile_result(monkeypatch, tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    stack = DemStack(layers=(DemLayer(path=dem_path, priority=0, aoi=None, nodata=-9999.0),))

    def fake_write_tile_dem(*args, **kwargs):
        return None

    def fake_prepare_sources(*args, **kwargs):
        return (dem_path,)

    monkeypatch.setattr(pipeline, "write_tile_dem", fake_write_tile_dem)
    monkeypatch.setattr(pipeline, "_prepare_sources", fake_prepare_sources)

    with pytest.raises(ValueError, match="No stack layers generated"):
        pipeline.normalize_stack_for_tiles(
            stack,
            ["+47+008"],
            tmp_path / "work",
            target_crs="EPSG:4326",
        )
