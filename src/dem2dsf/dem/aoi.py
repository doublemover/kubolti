"""AOI helpers for GeoJSON/shapefile bounds and masking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from pyproj import CRS

from dem2dsf.dem.crs import normalize_crs, transformer

DEFAULT_AOI_CRS = "EPSG:4326"


@dataclass(frozen=True)
class AoiData:
    """Normalized AOI shapes and CRS metadata."""

    path: Path
    shapes: list[dict[str, object]]
    crs: str
    crs_source: str
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _extract_geojson_shapes(data: dict[str, Any]) -> list[dict[str, object]]:
    shapes: list[dict[str, object]] = []
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features", []):
            geometry = feature.get("geometry")
            if geometry:
                shapes.append(geometry)
    elif data.get("type") == "Feature":
        geometry = data.get("geometry")
        if geometry:
            shapes.append(geometry)
    elif data.get("type") in {"Polygon", "MultiPolygon"}:
        shapes.append(data)
    return shapes


def _extract_geojson_crs(data: dict[str, Any]) -> str | None:
    crs = data.get("crs")
    if isinstance(crs, dict):
        properties = crs.get("properties")
        if isinstance(properties, dict):
            name = properties.get("name")
            if isinstance(name, str):
                return name
    if isinstance(crs, str):
        return crs
    return None


def _read_geojson(path: Path) -> tuple[list[dict[str, object]], str | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("AOI file must be a GeoJSON object.")
    shapes = _extract_geojson_shapes(data)
    return shapes, _extract_geojson_crs(data)


def _read_shapefile(path: Path) -> tuple[list[dict[str, object]], str | None]:
    try:
        import fiona  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError("Shapefile AOI requires the optional 'fiona' dependency.") from exc
    shapes: list[dict[str, object]] = []
    crs_value: str | None = None
    with fiona.open(path) as dataset:
        crs_value = dataset.crs_wkt or None
        if crs_value is None and dataset.crs:
            crs_value = CRS.from_user_input(dataset.crs).to_string()
        for feature in dataset:
            geometry = feature.get("geometry")
            if geometry:
                shapes.append(geometry)
    return shapes, crs_value


def _crs_equal(left: str, right: str) -> bool:
    return normalize_crs(left) == normalize_crs(right)


def _resolve_crs(
    embedded: str | None,
    explicit: str | None,
) -> tuple[str, str, tuple[str, ...]]:
    warnings: list[str] = []
    if explicit and embedded and not _crs_equal(explicit, embedded):
        warnings.append(f"AOI CRS mismatch: embedded {embedded} differs from --aoi-crs {explicit}.")
        return explicit, "explicit", tuple(warnings)
    if explicit:
        return explicit, "explicit", tuple(warnings)
    if embedded:
        return embedded, "embedded", tuple(warnings)
    warnings.append(f"AOI CRS missing; assuming {DEFAULT_AOI_CRS} (preferred).")
    return DEFAULT_AOI_CRS, "default", tuple(warnings)


def load_aoi(path: Path, *, crs: str | None = None) -> AoiData:
    """Load AOI shapes and CRS from GeoJSON or shapefile."""
    suffix = path.suffix.lower()
    if suffix in {".json", ".geojson"}:
        shapes, embedded = _read_geojson(path)
    elif suffix == ".shp":
        shapes, embedded = _read_shapefile(path)
    else:
        raise ValueError(f"Unsupported AOI format: {path.suffix}")

    if not shapes:
        raise ValueError(f"No polygon geometries found in {path}")

    resolved, source, warnings = _resolve_crs(embedded, crs)
    return AoiData(
        path=path,
        shapes=shapes,
        crs=resolved,
        crs_source=source,
        warnings=warnings,
    )


def load_aoi_shapes(path: Path, *, crs: str | None = None) -> list[dict[str, object]]:
    """Load AOI polygon geometries from a GeoJSON or shapefile."""
    return load_aoi(path, crs=crs).shapes


def bounds_from_shapes(shapes: Iterable[dict[str, object]]) -> tuple[float, float, float, float]:
    """Compute bounds from GeoJSON-like shapes."""
    xs: list[float] = []
    ys: list[float] = []

    def extract_coords(coords: Any) -> None:
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            xs.append(float(coords[0]))
            ys.append(float(coords[1]))
            return
        for part in coords:
            extract_coords(part)

    for shape in shapes:
        coords = shape.get("coordinates") if isinstance(shape, dict) else None
        if coords is not None:
            extract_coords(coords)

    if not xs or not ys:
        raise ValueError("AOI bounds could not be determined.")
    return (min(xs), min(ys), max(xs), max(ys))


def reproject_shapes(
    shapes: Iterable[dict[str, object]],
    src_crs: str,
    dst_crs: str,
) -> list[dict[str, object]]:
    """Reproject GeoJSON-like shapes between CRSs."""
    if _crs_equal(src_crs, dst_crs):
        return [dict(shape) for shape in shapes]
    tx = transformer(src_crs, dst_crs)

    def transform_coords(coords: Any) -> Any:
        if not coords:
            return coords
        if isinstance(coords[0], (int, float)):
            x, y = coords[0], coords[1]
            out_x, out_y = tx.transform(x, y)
            rest = list(coords[2:]) if len(coords) > 2 else []
            return [out_x, out_y, *rest]
        return [transform_coords(part) for part in coords]

    projected: list[dict[str, object]] = []
    for shape in shapes:
        if not isinstance(shape, dict):
            continue
        coords = shape.get("coordinates")
        if coords is None:
            continue
        updated = dict(shape)
        updated["coordinates"] = transform_coords(coords)
        projected.append(updated)
    return projected
