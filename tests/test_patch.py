from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

from dem2dsf.patch import (
    _apply_aoi_mask,
    _nodata_mask,
    _resolve_base_tile_path,
    apply_patch_to_tile,
    load_patch_plan,
    prepare_patch_tile,
    run_patch,
)
from tests.utils import write_raster


def test_load_patch_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "patch.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "patches": [
                    {"tile": "+47+008", "dem": "patch.tif", "aoi": "aoi.json"}
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = load_patch_plan(plan_path)

    assert plan.entries[0].tile == "+47+008"
    assert plan.entries[0].dem.name == "patch.tif"
    assert plan.entries[0].aoi and plan.entries[0].aoi.name == "aoi.json"


def test_apply_patch_to_tile(tmp_path: Path) -> None:
    base_path = tmp_path / "base.tif"
    patch_path = tmp_path / "patch.tif"
    base_data = np.array([[1, 1], [1, 1]], dtype=np.int16)
    patch_data = np.array([[-9999, 2], [2, -9999]], dtype=np.int16)
    write_raster(base_path, base_data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(patch_path, patch_data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)

    output_path = tmp_path / "out.tif"
    apply_patch_to_tile(base_path, patch_path, output_path)

    with rasterio.open(output_path) as dataset:
        data = dataset.read(1)
    assert data[0, 0] == 1
    assert data[0, 1] == 2


def test_prepare_patch_tile_with_aoi(tmp_path: Path) -> None:
    base_tile = tmp_path / "base.tif"
    patch_dem = tmp_path / "patch.tif"
    aoi_path = tmp_path / "aoi.json"
    data = np.array([[5, 5], [5, 5]], dtype=np.int16)
    write_raster(base_tile, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
    write_raster(patch_dem, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=-9999)
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

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "patches": [
                    {
                        "tile": "+47+008",
                        "dem": str(patch_dem),
                        "aoi": str(aoi_path),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    entry = load_patch_plan(plan_path).entries[0]

    tile = prepare_patch_tile(entry, base_tile, tmp_path / "work", resampling="nearest")

    with rasterio.open(tile) as dataset:
        values = dataset.read(1)
        assert (values == -9999).sum() > 0


def test_run_patch_dry_run(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    base_tile = build_dir / "normalized" / "tiles" / "+47+008" / "+47+008.tif"
    write_raster(
        base_tile,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    build_plan = {
        "schema_version": "0.2",
        "backend": {"name": "ortho4xp"},
        "inputs": {"dems": ["base.tif"]},
        "options": {"tile_dem_paths": {"+47+008": str(base_tile)}, "resampling": "nearest"},
    }
    (build_dir / "build_plan.json").write_text(
        json.dumps(build_plan), encoding="utf-8"
    )

    patch_plan = tmp_path / "patch.json"
    patch_dem = tmp_path / "patch_dem.tif"
    write_raster(
        patch_dem,
        np.array([[2]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    patch_plan.write_text(
        json.dumps({"patches": [{"tile": "+47+008", "dem": str(patch_dem)}]}),
        encoding="utf-8",
    )

    report = run_patch(
        build_dir=build_dir,
        patch_plan_path=patch_plan,
        dry_run=True,
    )

    output_dir = Path(report["output_dir"])
    assert (output_dir / "patch_report.json").exists()
    assert (output_dir / "build_plan.json").exists()


def test_load_patch_plan_requires_entries(tmp_path: Path) -> None:
    plan_path = tmp_path / "patch.json"
    plan_path.write_text(json.dumps({"patches": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty patches"):
        load_patch_plan(plan_path)


def test_load_patch_plan_requires_object(tmp_path: Path) -> None:
    plan_path = tmp_path / "patch.json"
    plan_path.write_text(json.dumps(["bad"]), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_patch_plan(plan_path)


def test_load_patch_plan_requires_dict_entry(tmp_path: Path) -> None:
    plan_path = tmp_path / "patch.json"
    plan_path.write_text(json.dumps({"patches": ["bad"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="Patch entry must be an object"):
        load_patch_plan(plan_path)


def test_load_patch_plan_requires_tile_and_dem(tmp_path: Path) -> None:
    plan_path = tmp_path / "patch.json"
    plan_path.write_text(json.dumps({"patches": [{"tile": "+47+008"}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="requires tile and dem"):
        load_patch_plan(plan_path)


def test_load_patch_plan_coerces_nodata(tmp_path: Path) -> None:
    plan_path = tmp_path / "patch.json"
    plan_path.write_text(
        json.dumps({"patches": [{"tile": "+47+008", "dem": "a.tif", "nodata": "5"}]}),
        encoding="utf-8",
    )

    plan = load_patch_plan(plan_path)
    assert plan.entries[0].nodata == 5.0


def test_prepare_patch_tile_requires_crs(tmp_path: Path) -> None:
    base_tile = tmp_path / "base.tif"
    data = np.array([[1]], dtype=np.int16)
    write_raster(base_tile, data, bounds=(8.0, 47.0, 9.0, 48.0))

    patch_dem = tmp_path / "patch.tif"
    transform = rasterio.transform.from_bounds(8.0, 47.0, 9.0, 48.0, 1, 1)
    with rasterio.open(
        patch_dem,
        "w",
        driver="GTiff",
        height=1,
        width=1,
        count=1,
        dtype=data.dtype,
        transform=transform,
    ) as dataset:
        dataset.write(data, 1)

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({"patches": [{"tile": "+47+008", "dem": str(patch_dem)}]}),
        encoding="utf-8",
    )
    entry = load_patch_plan(plan_path).entries[0]

    with pytest.raises(ValueError, match="missing CRS"):
        prepare_patch_tile(entry, base_tile, tmp_path / "work")


def test_prepare_patch_tile_warp(monkeypatch, tmp_path: Path) -> None:
    base_tile = tmp_path / "base.tif"
    data = np.array([[1]], dtype=np.int16)
    write_raster(base_tile, data, bounds=(8.0, 47.0, 9.0, 48.0))

    patch_dem = tmp_path / "patch.tif"
    write_raster(
        patch_dem,
        data,
        bounds=(8.0, 47.0, 9.0, 48.0),
        crs="EPSG:3857",
    )

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps({"patches": [{"tile": "+47+008", "dem": str(patch_dem)}]}),
        encoding="utf-8",
    )
    entry = load_patch_plan(plan_path).entries[0]

    called = {}

    def fake_warp(src, dst, crs, resolution, resampling, dst_nodata):
        called["crs"] = crs
        write_raster(
            dst,
            np.array([[1]], dtype=np.int16),
            bounds=(8.0, 47.0, 9.0, 48.0),
            crs=crs,
            nodata=dst_nodata,
        )

    monkeypatch.setattr("dem2dsf.patch.warp_dem", fake_warp)

    tile_path = prepare_patch_tile(entry, base_tile, tmp_path / "work")
    assert tile_path.exists()
    assert called["crs"] == "EPSG:4326"


def test_prepare_patch_tile_requires_nodata_for_aoi(tmp_path: Path) -> None:
    base_tile = tmp_path / "base.tif"
    patch_dem = tmp_path / "patch.tif"
    data = np.array([[1]], dtype=np.int16)
    write_raster(base_tile, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=None)
    write_raster(patch_dem, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=None)

    aoi_path = tmp_path / "aoi.json"
    aoi_path.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [[8, 47], [9, 47], [9, 48], [8, 48], [8, 47]]
                ],
            }
        ),
        encoding="utf-8",
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "patches": [
                    {"tile": "+47+008", "dem": str(patch_dem), "aoi": str(aoi_path)}
                ]
            }
        ),
        encoding="utf-8",
    )
    entry = load_patch_plan(plan_path).entries[0]

    with pytest.raises(ValueError, match="AOI mask requires a nodata value"):
        prepare_patch_tile(entry, base_tile, tmp_path / "work")


def test_nodata_mask_nan() -> None:
    data = np.array([[1.0, np.nan]], dtype=np.float32)
    mask = _nodata_mask(data, float("nan"))
    assert mask[0, 1]


def test_nodata_mask_none() -> None:
    data = np.array([[1.0]], dtype=np.float32)
    assert not _nodata_mask(data, None).any()


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

    _apply_aoi_mask(tile_path, shapes, -9999.0)
    with rasterio.open(tile_path) as dataset:
        assert dataset.read(1)[0, 0] == 1


def test_resolve_base_tile_path_normalized(tmp_path: Path) -> None:
    normalized = tmp_path / "normalized" / "tiles" / "+47+008" / "+47+008.tif"
    write_raster(
        normalized,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    options = {"tile_dem_paths": {"+47+008": "missing.tif"}}

    assert _resolve_base_tile_path(tmp_path, options, "+47+008") == normalized


def test_resolve_base_tile_path_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Base tile DEM not found"):
        _resolve_base_tile_path(tmp_path, {}, "+47+008")


def test_run_patch_requires_build_plan(tmp_path: Path) -> None:
    patch_plan = tmp_path / "patch.json"
    patch_plan.write_text(json.dumps({"patches": [{"tile": "+47+008", "dem": "a.tif"}]}))

    with pytest.raises(FileNotFoundError, match="Missing build_plan"):
        run_patch(build_dir=tmp_path, patch_plan_path=patch_plan)


def test_run_patch_requires_backend_name(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "build_plan.json").write_text(
        json.dumps({"schema_version": "1", "backend": {}}),
        encoding="utf-8",
    )
    patch_plan = tmp_path / "patch.json"
    patch_plan.write_text(
        json.dumps({"patches": [{"tile": "+47+008", "dem": "a.tif"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing backend name"):
        run_patch(build_dir=build_dir, patch_plan_path=patch_plan)


def test_run_patch_applies_overrides(monkeypatch, tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    base_tile = build_dir / "normalized" / "tiles" / "+47+008" / "+47+008.tif"
    write_raster(
        base_tile,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    build_plan = {
        "schema_version": "1",
        "backend": {"name": "ortho4xp"},
        "inputs": {"dems": ["base.tif"]},
        "options": {"tile_dem_paths": {"+47+008": str(base_tile)}},
    }
    (build_dir / "build_plan.json").write_text(
        json.dumps(build_plan), encoding="utf-8"
    )

    patch_plan = tmp_path / "patch.json"
    patch_dem = tmp_path / "patch_dem.tif"
    write_raster(
        patch_dem,
        np.array([[2]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    patch_plan.write_text(
        json.dumps({"patches": [{"tile": "+47+008", "dem": str(patch_dem)}]}),
        encoding="utf-8",
    )

    captured = {}

    def fake_run_build(*, options, **_kwargs):
        captured.update(options)

    monkeypatch.setattr("dem2dsf.patch.run_build", fake_run_build)

    run_patch(
        build_dir=build_dir,
        patch_plan_path=patch_plan,
        options_override={"density": "low"},
        dry_run=True,
    )

    assert captured["density"] == "low"
