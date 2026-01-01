"""Shared backend types and protocol for build runners."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class BackendSpec:
    """Describe backend capabilities and schema compatibility."""

    name: str
    version: str
    artifact_schema_version: str
    tile_dem_crs: str
    supports_xp12_rasters: bool
    supports_autoortho: bool


@dataclass(frozen=True)
class BuildRequest:
    """Inputs required to perform a backend build."""

    tiles: tuple[str, ...]
    dem_paths: tuple[Path, ...]
    output_dir: Path
    options: Mapping[str, Any]


@dataclass(frozen=True)
class BuildResult:
    """Build plan and report payloads emitted by backends."""

    build_plan: Mapping[str, Any]
    build_report: Mapping[str, Any]


class Backend(Protocol):
    """Protocol implemented by backend adapters."""

    def spec(self) -> BackendSpec:
        ...

    def build(self, request: BuildRequest) -> BuildResult:
        ...
