"""Backend-specific DEM profile adjustments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

from dem2dsf.dem.crs import normalize_crs


@dataclass(frozen=True)
class BackendProfile:
    """Expected DEM profile constraints for a backend."""

    name: str
    crs: str
    nodata: float | None
    require_full_coverage: bool


ORTHO4XP_PROFILE = BackendProfile(
    name="ortho4xp",
    crs="EPSG:4326",
    nodata=-32768.0,
    require_full_coverage=False,
)

PROFILE_BY_BACKEND = {
    "ortho4xp": ORTHO4XP_PROFILE,
}


def profile_for_backend(name: str) -> BackendProfile | None:
    """Return the profile for a named backend, if known."""
    return PROFILE_BY_BACKEND.get(name)


def apply_backend_profile(
    src_path: Path,
    dst_path: Path,
    profile: BackendProfile,
) -> None:
    """Rewrite a DEM to satisfy backend profile requirements."""
    with rasterio.open(src_path) as src:
        if src.crs is None:
            raise ValueError("Source DEM must declare a CRS.")
        if src.crs != normalize_crs(profile.crs):
            raise ValueError("Source DEM CRS must match backend CRS.")
        src_nodata = src.nodata
        nodata = profile.nodata if profile.nodata is not None else src_nodata
        meta = src.meta.copy()
        meta.update({"nodata": nodata})
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if profile.require_full_coverage and nodata is not None:
            for _, window in src.block_windows(1):
                data = src.read(1, window=window)
                if np.isnan(nodata):
                    if np.isnan(data).any():
                        raise ValueError("Backend profile requires void-free DEMs.")
                elif np.any(data == nodata):
                    raise ValueError("Backend profile requires void-free DEMs.")
        with rasterio.open(dst_path, "w", **meta) as dest:
            for _, window in src.block_windows(1):
                data = src.read(1, window=window)
                if (
                    profile.nodata is not None
                    and src_nodata is not None
                    and profile.nodata != src_nodata
                ):
                    data = data.copy()
                    if np.isnan(src_nodata):
                        data[np.isnan(data)] = profile.nodata
                    else:
                        data[data == src_nodata] = profile.nodata
                dest.write(data, 1, window=window)
