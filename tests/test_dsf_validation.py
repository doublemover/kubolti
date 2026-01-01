from __future__ import annotations

import pytest

from dem2dsf.dsf import compare_bounds, expected_bounds_for_tile, parse_bounds, parse_properties


def test_parse_bounds_matches_tile() -> None:
    text = "\n".join(
        [
            "PROPERTY sim/west -122",
            "PROPERTY sim/south 47",
            "PROPERTY sim/east -121",
            "PROPERTY sim/north 48",
        ]
    )
    properties = parse_properties(text)
    actual = parse_bounds(properties)
    expected = expected_bounds_for_tile("+47-122")
    assert compare_bounds(expected, actual) == []


def test_parse_properties_ignores_invalid_lines() -> None:
    text = "\n".join(
        [
            "PROPERTY sim/west",
            "NOT_PROPERTY sim/south 0",
            "PROPERTY sim/north 48",
        ]
    )
    properties = parse_properties(text)
    assert "sim/west" not in properties
    assert properties["sim/north"] == "48"


def test_parse_bounds_missing_property() -> None:
    properties = {"sim/west": "0", "sim/south": "0", "sim/east": "1"}
    with pytest.raises(ValueError, match="Missing DSF bounds properties"):
        parse_bounds(properties)


def test_parse_bounds_invalid_value() -> None:
    properties = {
        "sim/west": "bad",
        "sim/south": "0",
        "sim/east": "1",
        "sim/north": "1",
    }
    with pytest.raises(ValueError, match="Invalid DSF bounds value"):
        parse_bounds(properties)


def test_compare_bounds_reports_mismatch() -> None:
    text = "\n".join(
        [
            "PROPERTY sim/west 0",
            "PROPERTY sim/south 0",
            "PROPERTY sim/east 1",
            "PROPERTY sim/north 1",
        ]
    )
    properties = parse_properties(text)
    actual = parse_bounds(properties)
    expected = expected_bounds_for_tile("+02+003")
    mismatches = compare_bounds(expected, actual)
    assert mismatches
