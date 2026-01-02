"""Normalization cache helpers for DEM processing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from dem2dsf.dem.models import CoverageMetrics

CACHE_VERSION = 2


def _sha256_path(path: Path) -> str:
    """Return the SHA-256 checksum for a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _fingerprints_match(
    current: "SourceFingerprint",
    cached: "SourceFingerprint",
    *,
    validate_hashes: bool,
) -> bool:
    """Compare fingerprints, optionally requiring SHA-256 matches."""
    if (
        current.path != cached.path
        or current.size != cached.size
        or current.mtime_ns != cached.mtime_ns
    ):
        return False
    if validate_hashes:
        if not cached.sha256:
            return False
        return cached.sha256 == current.sha256
    return True


@dataclass(frozen=True)
class SourceFingerprint:
    """File metadata used to validate normalization cache inputs."""

    path: str
    size: int
    mtime_ns: int
    sha256: str | None = None

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        compute_sha256: bool = False,
    ) -> "SourceFingerprint":
        resolved = path.resolve()
        stat = resolved.stat()
        digest = _sha256_path(resolved) if compute_sha256 else None
        return cls(
            path=str(resolved),
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            sha256=digest,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceFingerprint":
        return cls(
            path=str(data["path"]),
            size=int(data["size"]),
            mtime_ns=int(data["mtime_ns"]),
            sha256=data.get("sha256"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.sha256 is None:
            payload.pop("sha256", None)
        return payload


def fingerprint_paths(
    paths: Iterable[Path],
    *,
    compute_sha256: bool = False,
) -> tuple[SourceFingerprint, ...]:
    """Return sorted fingerprints for a path collection."""
    fingerprints = [
        SourceFingerprint.from_path(path, compute_sha256=compute_sha256) for path in paths
    ]
    fingerprints.sort(key=lambda item: item.path)
    return tuple(fingerprints)


def fingerprint_path_map(
    paths: Mapping[str, Path],
    *,
    compute_sha256: bool = False,
) -> dict[str, SourceFingerprint]:
    """Return fingerprints keyed by map keys."""
    return {
        key: SourceFingerprint.from_path(path, compute_sha256=compute_sha256)
        for key, path in paths.items()
    }


@dataclass(frozen=True)
class NormalizationCache:
    """Persisted normalization cache data."""

    version: int
    sources: tuple[SourceFingerprint, ...]
    fallback_sources: tuple[SourceFingerprint, ...]
    options: dict[str, Any]
    tiles: tuple[str, ...]
    tile_paths: dict[str, str]
    tile_fingerprints: dict[str, SourceFingerprint]
    mosaic_path: str
    mosaic_fingerprint: SourceFingerprint | None
    coverage: dict[str, CoverageMetrics]

    def matches_inputs(
        self,
        *,
        sources: Iterable[Path],
        fallback_sources: Iterable[Path],
        options: Mapping[str, Any],
        validate_hashes: bool = False,
    ) -> bool:
        """Return True when the cache matches the current inputs/options."""
        if self.version != CACHE_VERSION:
            return False
        if self.options != dict(options):
            return False
        current_sources = fingerprint_paths(sources, compute_sha256=validate_hashes)
        current_fallback = fingerprint_paths(fallback_sources, compute_sha256=validate_hashes)
        if len(current_sources) != len(self.sources):
            return False
        if len(current_fallback) != len(self.fallback_sources):
            return False
        for current, cached in zip(current_sources, self.sources):
            if not _fingerprints_match(current, cached, validate_hashes=validate_hashes):
                return False
        for current, cached in zip(current_fallback, self.fallback_sources):
            if not _fingerprints_match(current, cached, validate_hashes=validate_hashes):
                return False
        return True

    def matches(
        self,
        *,
        sources: Iterable[Path],
        fallback_sources: Iterable[Path],
        options: Mapping[str, Any],
        tiles: Iterable[str],
        validate_hashes: bool = False,
    ) -> bool:
        """Return True when the cache matches the current inputs/options."""
        if not self.matches_inputs(
            sources=sources,
            fallback_sources=fallback_sources,
            options=options,
            validate_hashes=validate_hashes,
        ):
            return False
        tile_list = tuple(tiles)
        if self.tiles != tile_list:
            return False
        cached, missing = self.resolve_tiles(tile_list, validate_hashes=validate_hashes)
        return not missing and len(cached) == len(tile_list)

    def resolve_tiles(
        self,
        tiles: Iterable[str],
        *,
        validate_hashes: bool = False,
    ) -> tuple[dict[str, str], list[str]]:
        """Return cached tile paths plus any missing tiles."""
        cached: dict[str, str] = {}
        missing: list[str] = []
        for tile in tiles:
            path = self.tile_paths.get(tile)
            fingerprint = self.tile_fingerprints.get(tile)
            if not path or fingerprint is None:
                missing.append(tile)
                continue
            tile_path = Path(path)
            if not tile_path.exists():
                missing.append(tile)
                continue
            current = SourceFingerprint.from_path(
                tile_path,
                compute_sha256=validate_hashes,
            )
            if not _fingerprints_match(current, fingerprint, validate_hashes=validate_hashes):
                missing.append(tile)
                continue
            cached[tile] = path
        return cached, missing

    def mosaic_valid(self, *, validate_hashes: bool = False) -> bool:
        """Return True when the cached mosaic path is still valid."""
        if not self.mosaic_path:
            return False
        mosaic_path = Path(self.mosaic_path)
        if not mosaic_path.exists():
            return False
        if not validate_hashes:
            return True
        if self.mosaic_fingerprint is None:
            return False
        current = SourceFingerprint.from_path(mosaic_path, compute_sha256=True)
        return _fingerprints_match(current, self.mosaic_fingerprint, validate_hashes=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sources": [item.to_dict() for item in self.sources],
            "fallback_sources": [item.to_dict() for item in self.fallback_sources],
            "options": self.options,
            "tiles": list(self.tiles),
            "tile_paths": self.tile_paths,
            "tile_fingerprints": {
                tile: fingerprint.to_dict() for tile, fingerprint in self.tile_fingerprints.items()
            },
            "mosaic_path": self.mosaic_path,
            "mosaic_fingerprint": self.mosaic_fingerprint.to_dict()
            if self.mosaic_fingerprint is not None
            else None,
            "coverage": {tile: asdict(metrics) for tile, metrics in self.coverage.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NormalizationCache":
        sources = tuple(SourceFingerprint.from_dict(item) for item in data.get("sources", []))
        fallback_sources = tuple(
            SourceFingerprint.from_dict(item) for item in data.get("fallback_sources", [])
        )
        tile_fingerprints = {
            tile: SourceFingerprint.from_dict(payload)
            for tile, payload in data.get("tile_fingerprints", {}).items()
        }
        mosaic_fingerprint_payload = data.get("mosaic_fingerprint")
        mosaic_fingerprint = (
            SourceFingerprint.from_dict(mosaic_fingerprint_payload)
            if isinstance(mosaic_fingerprint_payload, dict)
            else None
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
            tile_fingerprints=tile_fingerprints,
            mosaic_path=str(data["mosaic_path"]),
            mosaic_fingerprint=mosaic_fingerprint,
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


def write_normalization_cache(work_dir: Path, cache: NormalizationCache) -> Path:
    """Write a normalization cache file and return its path."""
    path = cache_path(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache.to_dict(), indent=2), encoding="utf-8")
    return path
