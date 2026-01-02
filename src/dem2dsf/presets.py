"""Preset library for common datasets and regions."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class Preset:
    """Named preset with input hints and default options."""

    name: str
    summary: str
    inputs: tuple[str, ...]
    options: Mapping[str, Any]
    notes: tuple[str, ...]
    example: str


ENV_PRESETS_PATH = "DEM2DSF_PRESETS_PATH"
PRESET_FORMAT_VERSION = 1

_PRESETS: dict[str, Preset] = {
    "usgs-13as": Preset(
        name="usgs-13as",
        summary="USGS 1/3 arc-second for North America, denser mesh.",
        inputs=("USGS 1/3 arc-second GeoTIFF",),
        options={
            "backend": "ortho4xp",
            "quality": "compat",
            "density": "high",
            "resampling": "bilinear",
            "target_crs": "EPSG:4326",
            "fill_strategy": "none",
        },
        notes=("Good default for continental US tiles; adjust density per area.",),
        example=(
            "python -m dem2dsf build --dem <usgs_dem.tif> --tile +DD+DDD "
            "--density high --resampling bilinear"
        ),
    ),
    "eu-dem-utm": Preset(
        name="eu-dem-utm",
        summary="EU-DEM in ETRS89/UTM with reprojection and interpolation fill.",
        inputs=("EU-DEM UTM GeoTIFF (ETRS89)",),
        options={
            "backend": "ortho4xp",
            "quality": "compat",
            "density": "medium",
            "resampling": "cubic",
            "target_crs": "EPSG:4326",
            "fill_strategy": "interpolate",
        },
        notes=("Set target CRS to EPSG:4326; keep interpolation for small voids.",),
        example=(
            "python -m dem2dsf build --dem <eu_dem_utm.tif> --tile +DD+DDD "
            "--target-crs EPSG:4326 --resampling cubic --fill-strategy interpolate"
        ),
    ),
    "srtm-fallback": Preset(
        name="srtm-fallback",
        summary="SRTM global coverage with fallback DEMs for voids.",
        inputs=("SRTM global mosaic", "Fallback DEM (ALOS/ASTER)"),
        options={
            "backend": "ortho4xp",
            "quality": "compat",
            "density": "medium",
            "resampling": "bilinear",
            "fill_strategy": "fallback",
        },
        notes=("Add one or more fallback DEMs to fill voids reliably.",),
        example=(
            "python -m dem2dsf build --dem <srtm.tif> --fallback-dem <alos.tif> "
            "--tile +DD+DDD --fill-strategy fallback"
        ),
    ),
    "lidar-stack": Preset(
        name="lidar-stack",
        summary="Local LiDAR stack over a global DEM using a JSON stack file.",
        inputs=("LiDAR tile(s)", "Global DEM base"),
        options={
            "backend": "ortho4xp",
            "quality": "compat",
            "density": "high",
            "resampling": "bilinear",
            "fill_strategy": "none",
        },
        notes=("Use a DEM stack JSON to blend LiDAR over base coverage.",),
        example=("python -m dem2dsf build --dem-stack stack.json --tile +DD+DDD --density high"),
    ),
}


def default_user_presets_path() -> Path:
    """Return the default user preset file path."""
    return Path.home() / ".dem2dsf" / "presets.json"


def _candidate_preset_paths(explicit_path: Path | None) -> list[Path]:
    """Return candidate preset config locations in priority order."""
    if explicit_path is not None:
        return [explicit_path]
    candidates: list[Path] = []
    env_path = os.environ.get(ENV_PRESETS_PATH)
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(default_user_presets_path())
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "presets" / "presets.json")
    return candidates


def _coerce_str_list(value: Any) -> tuple[str, ...]:
    """Normalize a list-like value into a tuple of strings."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if item)
    return ()


def _preset_from_mapping(data: Mapping[str, Any]) -> Preset | None:
    """Build a Preset from a mapping, returning None for invalid entries."""
    name = data.get("name")
    summary = data.get("summary")
    if not isinstance(name, str) or not isinstance(summary, str):
        return None
    inputs = _coerce_str_list(data.get("inputs"))
    notes = _coerce_str_list(data.get("notes"))
    raw_options = data.get("options")
    options: dict[str, Any] = {}
    if isinstance(raw_options, Mapping):
        options = {str(key): value for key, value in raw_options.items()}
    example_value = data.get("example")
    example = example_value if isinstance(example_value, str) else ""
    return Preset(
        name=name.strip().lower(),
        summary=summary.strip(),
        inputs=inputs,
        options=options,
        notes=notes,
        example=example,
    )


def _presets_from_payload(payload: Any) -> dict[str, Preset]:
    """Parse a preset payload into a mapping keyed by name."""
    items: list[Mapping[str, Any]]
    if isinstance(payload, dict) and isinstance(payload.get("presets"), list):
        items = [item for item in payload["presets"] if isinstance(item, Mapping)]
    elif isinstance(payload, list):
        items = [item for item in payload if isinstance(item, Mapping)]
    else:
        return {}
    parsed: dict[str, Preset] = {}
    for item in items:
        preset = _preset_from_mapping(item)
        if preset:
            parsed[preset.name] = preset
    return parsed


def load_user_presets(path: Path | None = None) -> dict[str, Preset]:
    """Load user-defined presets from disk, if available."""
    for candidate in _candidate_preset_paths(path):
        if not candidate.exists():
            continue
        try:
            return load_presets_file(candidate)
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def load_presets_file(path: Path) -> dict[str, Preset]:
    """Load presets from an explicit JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _presets_from_payload(payload)


def serialize_presets(presets: Mapping[str, Preset]) -> dict[str, Any]:
    """Serialize presets to a JSON-compatible payload."""
    return {
        "version": PRESET_FORMAT_VERSION,
        "presets": [
            preset_as_dict(preset) for preset in sorted(presets.values(), key=lambda p: p.name)
        ],
    }


def write_user_presets(path: Path, presets: Mapping[str, Preset]) -> None:
    """Write user presets to disk in JSON format."""
    payload = serialize_presets(presets)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def list_presets(*, include_user: bool = True, user_path: Path | None = None) -> tuple[Preset, ...]:
    """Return all presets in sorted order."""
    merged = dict(_PRESETS)
    if include_user:
        merged.update(load_user_presets(user_path))
    return tuple(merged[name] for name in sorted(merged))


def get_preset(
    name: str, *, include_user: bool = True, user_path: Path | None = None
) -> Preset | None:
    """Return a preset by name, case-insensitive."""
    key = name.strip().lower()
    if include_user:
        user_presets = load_user_presets(user_path)
        if key in user_presets:
            return user_presets[key]
    return _PRESETS.get(key)


def preset_as_dict(preset: Preset) -> dict[str, Any]:
    """Return a JSON-serializable representation of a preset."""
    return {
        "name": preset.name,
        "summary": preset.summary,
        "inputs": list(preset.inputs),
        "options": dict(preset.options),
        "notes": list(preset.notes),
        "example": preset.example,
    }


def format_preset(preset: Preset) -> str:
    """Format a preset as a human-readable string."""
    lines = [f"Preset: {preset.name}", f"Summary: {preset.summary}"]
    if preset.inputs:
        lines.append("Inputs:")
        lines.extend([f"- {item}" for item in preset.inputs])
    if preset.options:
        lines.append("Defaults:")
        for key, value in sorted(preset.options.items()):
            lines.append(f"- {key}: {value}")
    if preset.notes:
        lines.append("Notes:")
        lines.extend([f"- {note}" for note in preset.notes])
    if preset.example:
        lines.append("Example:")
        lines.append(preset.example)
    return "\n".join(lines)
