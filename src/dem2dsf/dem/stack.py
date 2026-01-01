"""DEM stack configuration parsing and helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dem2dsf.dem.aoi import load_aoi_shapes as _load_aoi_shapes


@dataclass(frozen=True)
class DemLayer:
    """Single DEM layer entry in a stack."""

    path: Path
    priority: int
    aoi: Path | None
    nodata: float | None


@dataclass(frozen=True)
class DemStack:
    """Ordered set of DEM layers."""

    layers: tuple[DemLayer, ...]

    def sorted_layers(self) -> tuple[DemLayer, ...]:
        """Return layers sorted by priority (ascending)."""
        return tuple(sorted(self.layers, key=lambda layer: layer.priority))


def _coerce_layer(raw: dict[str, Any]) -> DemLayer:
    """Normalize a raw layer dict into a DemLayer."""
    if not isinstance(raw, dict):
        raise ValueError("Stack layer must be an object.")
    path = raw.get("path") or raw.get("dem")
    if not path:
        raise ValueError("Stack layer requires a path.")
    priority = raw.get("priority", 0)
    if not isinstance(priority, int):
        raise ValueError("Stack layer priority must be an integer.")
    aoi = raw.get("aoi")
    nodata = raw.get("nodata")
    if nodata is not None:
        nodata = float(nodata)
    return DemLayer(
        path=Path(path),
        priority=priority,
        aoi=Path(aoi) if aoi else None,
        nodata=nodata,
    )


def load_dem_stack(path: Path) -> DemStack:
    """Parse a DEM stack definition from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("DEM stack must be a JSON object.")
    raw_layers = data.get("layers")
    if not isinstance(raw_layers, list) or not raw_layers:
        raise ValueError("DEM stack requires a non-empty layers list.")
    layers = tuple(_coerce_layer(layer) for layer in raw_layers)
    return DemStack(layers=layers)


def stack_to_options(stack: DemStack) -> dict[str, Any]:
    """Convert a DemStack into options suitable for build metadata."""
    return {
        "layers": [
            {
                "path": str(layer.path),
                "priority": layer.priority,
                "aoi": str(layer.aoi) if layer.aoi else None,
                "nodata": layer.nodata,
            }
            for layer in stack.layers
        ]
    }


def load_aoi_shapes(path: Path) -> list[dict[str, Any]]:
    """Load AOI polygon geometries from a GeoJSON or shapefile."""
    return _load_aoi_shapes(path)
