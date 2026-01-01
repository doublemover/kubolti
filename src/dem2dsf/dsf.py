"""Helpers for parsing DSF properties and bounds."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dem2dsf.dem.tiling import tile_bounds


@dataclass(frozen=True)
class DsfBounds:
    """Geographic bounds parsed from a DSF properties section."""

    west: float
    south: float
    east: float
    north: float


def parse_properties(text: str) -> dict[str, str]:
    """Extract PROPERTY lines from DSFTool text output."""
    properties: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("PROPERTY"):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            continue
        properties[parts[1]] = parts[2]
    return properties


def parse_properties_from_file(path: Path) -> dict[str, str]:
    """Read a DSFTool properties file and parse PROPERTY lines."""
    return parse_properties(path.read_text(encoding="utf-8"))


def parse_bounds(properties: Mapping[str, str]) -> DsfBounds:
    """Parse DSF bound properties into a DsfBounds object."""
    required = ("sim/west", "sim/south", "sim/east", "sim/north")
    missing = [name for name in required if name not in properties]
    if missing:
        raise ValueError(f"Missing DSF bounds properties: {', '.join(missing)}")
    try:
        return DsfBounds(
            west=float(properties["sim/west"]),
            south=float(properties["sim/south"]),
            east=float(properties["sim/east"]),
            north=float(properties["sim/north"]),
        )
    except ValueError as exc:
        raise ValueError(f"Invalid DSF bounds value: {exc}") from exc


def expected_bounds_for_tile(tile: str) -> DsfBounds:
    """Return the expected DSF bounds for a tile name."""
    west, south, east, north = tile_bounds(tile)
    return DsfBounds(west=west, south=south, east=east, north=north)


def compare_bounds(
    expected: DsfBounds,
    actual: DsfBounds,
    *,
    tolerance: float = 1e-6,
) -> list[str]:
    """Compare expected vs actual bounds and return mismatch messages."""
    mismatches: list[str] = []
    if not math.isclose(expected.west, actual.west, abs_tol=tolerance):
        mismatches.append(f"west expected {expected.west}, got {actual.west}")
    if not math.isclose(expected.south, actual.south, abs_tol=tolerance):
        mismatches.append(f"south expected {expected.south}, got {actual.south}")
    if not math.isclose(expected.east, actual.east, abs_tol=tolerance):
        mismatches.append(f"east expected {expected.east}, got {actual.east}")
    if not math.isclose(expected.north, actual.north, abs_tol=tolerance):
        mismatches.append(f"north expected {expected.north}, got {actual.north}")
    return mismatches
