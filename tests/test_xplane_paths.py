from __future__ import annotations

import pytest

from dem2dsf.xplane_paths import (
    bucket_for_tile,
    dsf_path,
    elevation_data_path,
    hgt_tile_name,
    parse_tile,
    tile_from_dsf_path,
)


def test_parse_tile() -> None:
    assert parse_tile("+47+008") == (47, 8)
    assert parse_tile("-01-123") == (-1, -123)


def test_parse_tile_rejects_bad_names() -> None:
    with pytest.raises(ValueError, match="Invalid tile name"):
        parse_tile("47008")


def test_bucket_for_tile() -> None:
    assert bucket_for_tile("+47+008") == "+40+000"
    assert bucket_for_tile("-41+175") == "-50+170"


def test_dsf_path_and_tile_name(tmp_path) -> None:
    path = dsf_path(tmp_path, "+47+008")
    assert path.as_posix().endswith("Earth nav data/+40+000/+47+008.dsf")
    assert tile_from_dsf_path(path) == "+47+008"


def test_hgt_tile_name() -> None:
    assert hgt_tile_name("+47+008") == "N47E008"
    assert hgt_tile_name("-01-123") == "S01W123"


def test_elevation_data_path(tmp_path) -> None:
    path = elevation_data_path(tmp_path, "+47+008", ".tif")
    assert path.as_posix().endswith("Elevation_data/+40+000/N47E008.tif")
