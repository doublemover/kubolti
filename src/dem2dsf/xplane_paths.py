"""X-Plane scenery path helpers (tiles, buckets, DSF paths)."""

from __future__ import annotations

import math
from pathlib import Path

from dem2dsf.dem.tiling import tile_name


def parse_tile(tile: str) -> tuple[int, int]:
    """Parse a +DD+DDD tile name into integer latitude/longitude."""
    if len(tile) != 7 or tile[0] not in "+-" or tile[3] not in "+-":
        raise ValueError(f"Invalid tile name: {tile}")
    lat = int(tile[0:3])
    lon = int(tile[3:7])
    return lat, lon


def bucket_for_tile(tile: str) -> str:
    """Return the 10x10 bucket folder for a tile."""
    lat, lon = parse_tile(tile)
    bucket_lat = math.floor(lat / 10) * 10
    bucket_lon = math.floor(lon / 10) * 10
    return tile_name(bucket_lat, bucket_lon)


def hgt_tile_name(tile: str) -> str:
    """Return the N/S/E/W tile name used by Ortho4XP elevation files."""
    lat, lon = parse_tile(tile)
    lat_prefix = "N" if lat >= 0 else "S"
    lon_prefix = "E" if lon >= 0 else "W"
    return f"{lat_prefix}{abs(lat):02d}{lon_prefix}{abs(lon):03d}"


def elevation_data_path(root: Path, tile: str, suffix: str) -> Path:
    """Return the expected Elevation_data path for a custom DEM file."""
    return (
        root
        / "Elevation_data"
        / bucket_for_tile(tile)
        / f"{hgt_tile_name(tile)}{suffix}"
    )


def dsf_path(root: Path, tile: str) -> Path:
    """Return the expected DSF path beneath an Earth nav data root."""
    return root / "Earth nav data" / bucket_for_tile(tile) / f"{tile}.dsf"


def tile_from_dsf_path(dsf_path: Path) -> str:
    """Return the tile name from a DSF filename."""
    return dsf_path.stem


def bucket_from_dsf_path(dsf_path: Path) -> str:
    """Return the bucket folder name from a DSF path."""
    return dsf_path.parent.name
