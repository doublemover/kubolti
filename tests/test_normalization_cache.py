from __future__ import annotations

from pathlib import Path

from dem2dsf.dem.cache import (
    CACHE_VERSION,
    NormalizationCache,
    fingerprint_paths,
    load_normalization_cache,
    write_normalization_cache,
)
from dem2dsf.dem.models import CoverageMetrics


def test_normalization_cache_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "source.tif"
    fallback = tmp_path / "fallback.tif"
    source.write_text("source", encoding="utf-8")
    fallback.write_text("fallback", encoding="utf-8")

    tile_path = tmp_path / "normalized" / "tiles" / "+47+008" / "+47+008.tif"
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tile_path.write_text("tile", encoding="utf-8")

    mosaic_path = tmp_path / "normalized" / "mosaic.tif"
    mosaic_path.write_text("mosaic", encoding="utf-8")

    coverage = {
        "+47+008": CoverageMetrics(
            total_pixels=4,
            nodata_pixels_before=0,
            nodata_pixels_after=0,
            coverage_before=1.0,
            coverage_after=1.0,
            filled_pixels=0,
            strategy="none",
        )
    }
    cache = NormalizationCache(
        version=CACHE_VERSION,
        sources=fingerprint_paths([source]),
        fallback_sources=fingerprint_paths([fallback]),
        options={"target_crs": "EPSG:4326"},
        tiles=("+47+008",),
        tile_paths={"+47+008": str(tile_path)},
        mosaic_path=str(mosaic_path),
        coverage=coverage,
    )

    write_normalization_cache(tmp_path / "normalized", cache)
    loaded = load_normalization_cache(tmp_path / "normalized")

    assert loaded is not None
    assert loaded.matches(
        sources=[source],
        fallback_sources=[fallback],
        options={"target_crs": "EPSG:4326"},
        tiles=["+47+008"],
    )
    assert loaded.coverage["+47+008"].filled_pixels == 0
