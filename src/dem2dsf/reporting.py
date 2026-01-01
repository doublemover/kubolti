"""Build plan and report construction helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from dem2dsf.backends.base import BackendSpec
from dem2dsf.contracts import SCHEMA_VERSION


def _utc_now() -> str:
    """Return the current UTC timestamp as ISO8601."""
    return datetime.now(timezone.utc).isoformat()


def build_plan(
    *,
    backend: BackendSpec,
    tiles: Iterable[str],
    dem_paths: Iterable[str],
    options: Mapping[str, Any],
    aoi: str | None = None,
) -> dict[str, Any]:
    """Create a build plan dictionary."""
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _utc_now(),
        "inputs": {"dems": list(dem_paths), "aoi": aoi},
        "tiles": list(tiles),
        "backend": {
            "name": backend.name,
            "version": backend.version,
            "profile": options.get("quality"),
        },
        "options": dict(options),
        "notes": [],
    }


def build_report(
    *,
    backend: BackendSpec,
    tile_statuses: Iterable[Mapping[str, Any]],
    artifacts: Mapping[str, Any],
    warnings: Iterable[str],
    errors: Iterable[str],
) -> dict[str, Any]:
    """Create a build report dictionary."""
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _utc_now(),
        "backend": {"name": backend.name, "version": backend.version},
        "tiles": list(tile_statuses),
        "artifacts": dict(artifacts),
        "warnings": list(warnings),
        "errors": list(errors),
    }
