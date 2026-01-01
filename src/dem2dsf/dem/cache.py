"""Normalization cache helpers for DEM processing."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from dem2dsf.dem.models import CoverageMetrics

CACHE_VERSION = 1


@dataclass(frozen=True)
class SourceFingerprint:
    """File metadata used to validate normalization cache inputs."""

    path: str
    size: int
    mtime_ns: int

    @classmethod
    def from_path(cls, path: Path) -> "SourceFingerprint":
        resolved = path.resolve()
        stat = resolved.stat()
        return cls(path=str(resolved), size=stat.st_size, mtime_ns=stat.st_mtime_ns)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceFingerprint":
        return cls(
            path=str(data["path"]),
            size=int(data["size"]),
            mtime_ns=int(data["mtime_ns"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fingerprint_paths(paths: Iterable[Path]) -> tuple[SourceFingerprint, ...]:
    """Return sorted fingerprints for a path collection."""
    fingerprints = [SourceFingerprint.from_path(path) for path in paths]
    fingerprints.sort(key=lambda item: item.path)
    return tuple(fingerprints)


@dataclass(frozen=True)
class NormalizationCache:
    """Persisted normalization cache data."""

    version: int
    sources: tuple[SourceFingerprint, ...]
    fallback_sources: tuple[SourceFingerprint, ...]
    options: dict[str, Any]
    tiles: tuple[str, ...]
    tile_paths: dict[str, str]
    mosaic_path: str
    coverage: dict[str, CoverageMetrics]

    def matches(
        self,
        *,
        sources: Iterable[Path],
        fallback_sources: Iterable[Path],
        options: Mapping[str, Any],
        tiles: Iterable[str],
    ) -> bool:
        """Return True when the cache matches the current inputs/options."""
        if self.version != CACHE_VERSION:
            return False
        if self.options != dict(options):
            return False
        tile_list = tuple(tiles)
        if self.tiles != tile_list:
            return False
        if fingerprint_paths(sources) != self.sources:
            return False
        if fingerprint_paths(fallback_sources) != self.fallback_sources:
            return False
        if not Path(self.mosaic_path).exists():
            return False
        for tile in tile_list:
            path = self.tile_paths.get(tile)
            if not path or not Path(path).exists():
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sources": [item.to_dict() for item in self.sources],
            "fallback_sources": [item.to_dict() for item in self.fallback_sources],
            "options": self.options,
            "tiles": list(self.tiles),
            "tile_paths": self.tile_paths,
            "mosaic_path": self.mosaic_path,
            "coverage": {
                tile: asdict(metrics) for tile, metrics in self.coverage.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NormalizationCache":
        sources = tuple(
            SourceFingerprint.from_dict(item) for item in data.get("sources", [])
        )
        fallback_sources = tuple(
            SourceFingerprint.from_dict(item)
            for item in data.get("fallback_sources", [])
        )
        coverage = {}
        for tile, metrics in data.get("coverage", {}).items():
            payload = dict(metrics)
            payload.setdefault("normalize_seconds", 0.0)
            coverage[tile] = CoverageMetrics(**payload)
        return cls(
            version=int(data["version"]),
            sources=sources,
            fallback_sources=fallback_sources,
            options=dict(data.get("options", {})),
            tiles=tuple(data.get("tiles", [])),
            tile_paths=dict(data.get("tile_paths", {})),
            mosaic_path=str(data["mosaic_path"]),
            coverage=coverage,
        )


def cache_path(work_dir: Path) -> Path:
    """Return the path to the normalization cache file."""
    return work_dir / "normalization_cache.json"


def load_normalization_cache(work_dir: Path) -> NormalizationCache | None:
    """Load a normalization cache file if present and valid."""
    path = cache_path(work_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return NormalizationCache.from_dict(payload)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def write_normalization_cache(
    work_dir: Path, cache: NormalizationCache
) -> Path:
    """Write a normalization cache file and return its path."""
    path = cache_path(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache.to_dict(), indent=2), encoding="utf-8")
    return path
