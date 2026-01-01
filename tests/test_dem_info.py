from __future__ import annotations

import numpy as np

from dem2dsf.dem.info import inspect_dem
from tests.utils import write_raster


def test_inspect_dem(tmp_path) -> None:
    raster_path = tmp_path / "dem.tif"
    data = np.array([[1, 2], [3, 4]], dtype=np.int16)
    write_raster(raster_path, data, bounds=(0.0, 0.0, 1.0, 1.0), nodata=-9999)

    info = inspect_dem(raster_path)

    assert info.crs == "EPSG:4326"
    assert info.bounds == (0.0, 0.0, 1.0, 1.0)
    assert info.width == 2
    assert info.height == 2
    assert info.nodata == -9999
    assert info.resolution == (0.5, 0.5)
    assert info.dtype == "int16"
