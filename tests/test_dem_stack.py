from __future__ import annotations

import json
from pathlib import Path

import pytest

from dem2dsf.dem.stack import DemStack, load_aoi_shapes, load_dem_stack, stack_to_options


def test_load_dem_stack(tmp_path: Path) -> None:
    stack_path = tmp_path / "stack.json"
    stack_path.write_text(
        json.dumps(
            {
                "layers": [
                    {"path": "a.tif", "priority": 10, "aoi": "aoi.json"},
                    {"dem": "b.tif", "priority": 0},
                ]
            }
        ),
        encoding="utf-8",
    )

    stack = load_dem_stack(stack_path)

    assert isinstance(stack, DemStack)
    assert stack.layers[0].path.name == "a.tif"
    assert stack.layers[0].priority == 10
    assert stack.layers[0].aoi and stack.layers[0].aoi.name == "aoi.json"
    assert stack.layers[1].path.name == "b.tif"

    options = stack_to_options(stack)
    assert options["layers"][0]["path"].endswith("a.tif")


def test_load_dem_stack_requires_layers(tmp_path: Path) -> None:
    stack_path = tmp_path / "stack.json"
    stack_path.write_text(json.dumps({"layers": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="layers list"):
        load_dem_stack(stack_path)


def test_load_dem_stack_requires_object(tmp_path: Path) -> None:
    stack_path = tmp_path / "stack.json"
    stack_path.write_text(json.dumps(["bad"]), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_dem_stack(stack_path)


def test_load_dem_stack_invalid_layer(tmp_path: Path) -> None:
    stack_path = tmp_path / "stack.json"
    stack_path.write_text(json.dumps({"layers": ["bad"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="layer must be an object"):
        load_dem_stack(stack_path)


def test_load_dem_stack_invalid_priority(tmp_path: Path) -> None:
    stack_path = tmp_path / "stack.json"
    stack_path.write_text(
        json.dumps({"layers": [{"path": "a.tif", "priority": "high"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="priority must be an integer"):
        load_dem_stack(stack_path)


def test_load_dem_stack_requires_path(tmp_path: Path) -> None:
    stack_path = tmp_path / "stack.json"
    stack_path.write_text(
        json.dumps({"layers": [{"priority": 0}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a path"):
        load_dem_stack(stack_path)


def test_load_dem_stack_coerces_nodata(tmp_path: Path) -> None:
    stack_path = tmp_path / "stack.json"
    stack_path.write_text(
        json.dumps({"layers": [{"path": "a.tif", "priority": 0, "nodata": "5"}]}),
        encoding="utf-8",
    )

    stack = load_dem_stack(stack_path)

    assert stack.layers[0].nodata == 5.0


def test_load_aoi_shapes(tmp_path: Path) -> None:
    aoi_path = tmp_path / "aoi.json"
    aoi_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
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
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    shapes = load_aoi_shapes(aoi_path)

    assert shapes
    assert shapes[0]["type"] == "Polygon"


def test_load_aoi_shapes_requires_polygons(tmp_path: Path) -> None:
    aoi_path = tmp_path / "aoi.json"
    aoi_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No polygon"):
        load_aoi_shapes(aoi_path)


def test_load_aoi_shapes_feature(tmp_path: Path) -> None:
    aoi_path = tmp_path / "aoi.json"
    aoi_path.write_text(
        json.dumps(
            {
                "type": "Feature",
                "geometry": {
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
                },
            }
        ),
        encoding="utf-8",
    )

    shapes = load_aoi_shapes(aoi_path)

    assert shapes and shapes[0]["type"] == "Polygon"
