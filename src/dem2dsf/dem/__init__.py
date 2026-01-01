"""DEM processing helpers and exports."""

from dem2dsf.dem.adapter import ORTHO4XP_PROFILE, BackendProfile, profile_for_backend
from dem2dsf.dem.crs import normalize_crs, transform_bounds, transformer
from dem2dsf.dem.fill import fill_with_constant, fill_with_fallback, fill_with_interpolation
from dem2dsf.dem.info import inspect_dem
from dem2dsf.dem.models import CoverageMetrics, DemInfo, MosaicResult, TileResult, WarpResult
from dem2dsf.dem.mosaic import build_mosaic
from dem2dsf.dem.pipeline import NormalizationResult, normalize_for_tiles
from dem2dsf.dem.tiling import tile_bounds, tile_name, tiles_for_bounds, write_tile_dem
from dem2dsf.dem.warp import warp_dem

__all__ = [
    "BackendProfile",
    "CoverageMetrics",
    "DemInfo",
    "MosaicResult",
    "ORTHO4XP_PROFILE",
    "TileResult",
    "WarpResult",
    "build_mosaic",
    "NormalizationResult",
    "normalize_for_tiles",
    "fill_with_constant",
    "fill_with_fallback",
    "fill_with_interpolation",
    "inspect_dem",
    "normalize_crs",
    "profile_for_backend",
    "tile_bounds",
    "tile_name",
    "tiles_for_bounds",
    "transform_bounds",
    "transformer",
    "warp_dem",
    "write_tile_dem",
]
