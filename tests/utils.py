from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import numpy as np
import rasterio
from rasterio.transform import from_bounds


def write_raster(
    path: Path,
    data: np.ndarray,
    *,
    bounds: Tuple[float, float, float, float],
    crs: str = "EPSG:4326",
    nodata: float | None = None,
) -> None:
    height, width = data.shape
    transform = from_bounds(*bounds, width=width, height=height)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dataset:
        dataset.write(data, 1)


def with_src_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return an environment with repo src/ on PYTHONPATH."""
    env = dict(base_env or os.environ)
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if src_path.exists():
        existing = env.get("PYTHONPATH", "")
        entries = [entry for entry in existing.split(os.pathsep) if entry]
        src_str = str(src_path)
        if src_str not in entries:
            entries.insert(0, src_str)
        env["PYTHONPATH"] = os.pathsep.join(entries)
    return env
