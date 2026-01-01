from __future__ import annotations

import numpy as np
import pytest
import rasterio

from dem2dsf.dem.mosaic import build_mosaic
from tests.utils import write_raster


def test_build_mosaic_requires_inputs(tmp_path) -> None:
    with pytest.raises(ValueError, match="DEM path"):
        build_mosaic([], tmp_path / "out.tif")


def test_build_mosaic(tmp_path) -> None:
    left = tmp_path / "left.tif"
    right = tmp_path / "right.tif"
    write_raster(left, np.array([[1]], dtype=np.int16), bounds=(0.0, 0.0, 1.0, 1.0))
    write_raster(right, np.array([[2]], dtype=np.int16), bounds=(1.0, 0.0, 2.0, 1.0))

    output = tmp_path / "mosaic.tif"
    result = build_mosaic([left, right], output)

    assert result.crs == "EPSG:4326"
    assert result.bounds == (0.0, 0.0, 2.0, 1.0)
    assert result.resolution == (1.0, 1.0)

    with rasterio.open(output) as dataset:
        data = dataset.read(1)
    assert data.shape == (1, 2)
    assert data.tolist() == [[1, 2]]
