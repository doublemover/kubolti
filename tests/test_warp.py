from __future__ import annotations

import numpy as np
import rasterio

from dem2dsf.dem.warp import warp_dem
from tests.utils import write_raster


def test_warp_dem_same_crs(tmp_path) -> None:
    src = tmp_path / "src.tif"
    dst = tmp_path / "dst.tif"
    write_raster(src, np.array([[1]], dtype=np.int16), bounds=(0.0, 0.0, 1.0, 1.0))

    result = warp_dem(src, dst, "EPSG:4326", dst_nodata=-9999.0)

    assert result.crs == "EPSG:4326"
    with rasterio.open(dst) as dataset:
        assert dataset.nodata == -9999.0
        assert dataset.read(1)[0, 0] == 1
