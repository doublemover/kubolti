"""Build config loading and normalization helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from dem2dsf.contracts import validate_build_config


@dataclass(frozen=True)
class BuildConfig:
    """Normalized build configuration payload."""

    inputs: dict[str, Any]
    options: dict[str, Any]
    tools: dict[str, Any]
    output_dir: str | None = None
    schema_version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "inputs": dict(self.inputs),
            "options": dict(self.options),
            "tools": dict(self.tools),
        }
        if self.output_dir:
            payload["output_dir"] = self.output_dir
        if self.schema_version:
            payload["schema_version"] = self.schema_version
        return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_config_lock(
    *,
    inputs: Mapping[str, Any],
    options: Mapping[str, Any],
    tools: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Create a locked build config snapshot for a build run."""
    payload: dict[str, Any] = {
        "created_at": _utc_now(),
        "output_dir": str(output_dir),
        "inputs": dict(inputs),
        "options": dict(options),
        "tools": dict(tools),
    }
    return payload


def _normalize_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        return [value]
    raise TypeError("Expected string or list of strings.")


def _normalize_command(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    raise TypeError("Command must be a string or list of strings.")


def _merge_inputs(inputs: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key in ("dems", "dem_stack", "tiles", "aoi", "aoi_crs"):
        if key in source:
            inputs[key] = source[key]
    if "dem_stack_path" in source and "dem_stack" not in inputs:
        inputs["dem_stack"] = source["dem_stack_path"]


def normalize_build_config(payload: Mapping[str, Any]) -> BuildConfig:
    """Normalize a raw build config payload into canonical keys."""
    inputs: dict[str, Any] = {}
    options: dict[str, Any] = {}
    tools: dict[str, Any] = {}
    schema_version = payload.get("schema_version")
    output_dir = payload.get("output_dir") or payload.get("output")

    raw_inputs = payload.get("inputs")
    if isinstance(raw_inputs, Mapping):
        _merge_inputs(inputs, raw_inputs)

    _merge_inputs(inputs, payload)

    top_dems = payload.get("dems") or payload.get("dem")
    if top_dems is not None:
        inputs["dems"] = _normalize_list(top_dems)
    if "dems" in inputs:
        inputs["dems"] = _normalize_list(inputs["dems"])
    if "tiles" in inputs:
        inputs["tiles"] = _normalize_list(inputs["tiles"])
    if "dem_stack" in inputs and inputs["dem_stack"] is not None:
        inputs["dem_stack"] = str(inputs["dem_stack"])
    if "aoi" in inputs and inputs["aoi"] is not None:
        inputs["aoi"] = str(inputs["aoi"])
    if "aoi_crs" in inputs and inputs["aoi_crs"] is not None:
        inputs["aoi_crs"] = str(inputs["aoi_crs"])

    raw_options = payload.get("options")
    if isinstance(raw_options, Mapping):
        options.update(raw_options)
    if "fallback_dem" in options and "fallback_dem_paths" not in options:
        options["fallback_dem_paths"] = options.get("fallback_dem")
    if "fallback_dem_paths" in options:
        options["fallback_dem_paths"] = _normalize_list(options.get("fallback_dem_paths"))
    if "dem_stack" in inputs:
        options.setdefault("dem_stack_path", inputs["dem_stack"])

    raw_tools = payload.get("tools")
    if isinstance(raw_tools, Mapping):
        tools.update(raw_tools)
    for key in ("runner", "dsftool", "ddstool"):
        if key in payload:
            tools[key] = payload[key]
    normalized_tools: dict[str, Any] = {}
    for key in ("runner", "dsftool", "ddstool"):
        if key in tools and tools[key] is not None:
            normalized_tools[key] = _normalize_command(tools[key])

    return BuildConfig(
        inputs=inputs,
        options=options,
        tools=normalized_tools,
        output_dir=str(output_dir) if output_dir else None,
        schema_version=str(schema_version) if schema_version else None,
    )


def load_build_config(path: Path) -> BuildConfig:
    """Load and validate a build config file from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("Build config must be a JSON object.")
    config = normalize_build_config(payload)
    validate_build_config(config.as_dict())
    return config
