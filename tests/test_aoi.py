from __future__ import annotations

import json
from pathlib import Path

from dem2dsf.dem.aoi import DEFAULT_AOI_CRS, load_aoi


def _write_geojson(path: Path, *, crs: str | None = None) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
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
                },
            }
        ],
    }
    if crs:
        payload["crs"] = {"type": "name", "properties": {"name": crs}}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_aoi_defaults_to_wgs84(tmp_path: Path) -> None:
    aoi_path = tmp_path / "aoi.geojson"
    _write_geojson(aoi_path)

    aoi = load_aoi(aoi_path)

    assert aoi.crs == DEFAULT_AOI_CRS
    assert aoi.crs_source == "default"
    assert any("preferred" in warning for warning in aoi.warnings)


def test_load_aoi_uses_embedded_crs(tmp_path: Path) -> None:
    aoi_path = tmp_path / "aoi.geojson"
    _write_geojson(aoi_path, crs="EPSG:3857")

    aoi = load_aoi(aoi_path)

    assert aoi.crs == "EPSG:3857"
    assert aoi.crs_source == "embedded"
    assert aoi.warnings == ()


def test_load_aoi_explicit_overrides_embedded(tmp_path: Path) -> None:
    aoi_path = tmp_path / "aoi.geojson"
    _write_geojson(aoi_path, crs="EPSG:3857")

    aoi = load_aoi(aoi_path, crs="EPSG:4326")

    assert aoi.crs == "EPSG:4326"
    assert aoi.crs_source == "explicit"
    assert any("mismatch" in warning for warning in aoi.warnings)
