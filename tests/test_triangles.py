from __future__ import annotations

import numpy as np

from dem2dsf.triangles import estimate_triangles_from_raster
from tests.utils import write_raster


def test_estimate_triangles_from_raster(tmp_path) -> None:
    raster_path = tmp_path / "dem.tif"
    data = np.zeros((3, 4), dtype=np.int16)
    write_raster(raster_path, data, bounds=(0.0, 0.0, 1.0, 1.0))

    estimate = estimate_triangles_from_raster(raster_path)
    assert estimate.count == (4 - 1) * (3 - 1) * 2
    assert estimate.width == 4
    assert estimate.height == 3
