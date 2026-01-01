from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from dem2dsf.dem.pipeline import normalize_for_tiles
from tests.utils import write_raster


def test_normalize_applies_aoi_mask(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    data = np.ones((10, 10), dtype=np.int16)
    write_raster(dem_path, data, bounds=(0.0, 0.0, 1.0, 1.0), nodata=-9999)

    aoi_path = tmp_path / "aoi.geojson"
    aoi_path.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [0.0, 0.0],
                        [0.5, 0.0],
                        [0.5, 1.0],
                        [0.0, 1.0],
                        [0.0, 0.0],
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    result = normalize_for_tiles(
        [dem_path],
        ["+00+000"],
        tmp_path / "work",
        target_crs="EPSG:4326",
        dst_nodata=-9999,
        aoi_path=aoi_path,
    )

    tile_path = result.tile_results[0].path
    with rasterio.open(tile_path) as dataset:
        band = dataset.read(1)
    assert (band == -9999).any()
