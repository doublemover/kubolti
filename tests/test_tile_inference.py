from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dem2dsf.tile_inference import infer_tiles
from tests.utils import write_raster


def test_infer_tiles_from_dem_bounds(tmp_path: Path) -> None:
    dem_path = tmp_path / "dem.tif"
    data = np.array([[1, 2], [3, 4]], dtype=np.int16)
    write_raster(dem_path, data, bounds=(0.0, 0.0, 2.0, 1.0), nodata=-9999)

    result = infer_tiles([dem_path])

    assert result.tiles == ["+00+000", "+00+001"]
    assert result.dem_bounds == (0.0, 0.0, 2.0, 1.0)
    assert result.aoi_bounds is None
    assert result.coverage["+00+000"] == 1.0


def test_infer_tiles_from_aoi(tmp_path: Path) -> None:
    aoi_path = tmp_path / "aoi.geojson"
    aoi_path.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [10.2, 45.3],
                        [10.8, 45.3],
                        [10.8, 45.9],
                        [10.2, 45.9],
                        [10.2, 45.3],
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    result = infer_tiles([], aoi_path=aoi_path)

    assert result.tiles == ["+45+010"]
    assert result.aoi_bounds is not None
