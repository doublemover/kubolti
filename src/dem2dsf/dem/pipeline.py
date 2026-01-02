"""Normalization pipeline for DEM mosaics, tiling, and fill strategies."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable, Mapping

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.merge import merge

from dem2dsf.dem.adapter import BackendProfile
from dem2dsf.dem.crs import normalize_crs
from dem2dsf.dem.fill import (
    FillResult,
    fill_with_constant,
    fill_with_fallback,
    fill_with_interpolation,
)
from dem2dsf.dem.info import inspect_dem
from dem2dsf.dem.models import CoverageMetrics, DemInfo, TileResult
from dem2dsf.dem.mosaic import build_mosaic
from dem2dsf.dem.stack import DemStack, load_aoi_shapes
from dem2dsf.dem.tiling import tile_bounds, tile_bounds_in_crs, write_tile_dem
from dem2dsf.dem.warp import warp_dem


@dataclass(frozen=True)
class NormalizationResult:
    """Outputs from a normalization pass."""

    sources: tuple[Path, ...]
    target_crs: str
    mosaic_path: Path
    tile_results: tuple[TileResult, ...]
    coverage: Mapping[str, CoverageMetrics]
    errors: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TileWorkResult:
    """Per-tile normalization output or failure."""

    tile: str
    result: TileResult | None
    metrics: CoverageMetrics | None
    error: str | None


def _resampling(method: str) -> Resampling:
    """Return rasterio resampling enum for a method string."""
    return Resampling[method]


def _nodata_mask(data: np.ndarray, nodata: float | None) -> np.ndarray:
    """Return a boolean mask where nodata values are present."""
    if nodata is None:
        return np.zeros(data.shape, dtype=bool)
    if np.isnan(nodata):
        return np.isnan(data)
    return data == nodata


def _coerce_tile_jobs(tile_jobs: int, tile_count: int) -> int:
    """Normalize requested worker count for per-tile processing."""
    jobs = int(tile_jobs)
    if tile_count <= 0:
        return 1
    if jobs < 0:
        raise ValueError("tile_jobs must be >= 0")
    if jobs == 0:
        cpu_count = os.cpu_count() or 1
        return max(1, min(cpu_count, tile_count))
    return min(jobs, tile_count)


def _run_tile_jobs(
    tiles: list[str],
    tile_jobs: int,
    worker: Callable[[str], tuple[TileResult, CoverageMetrics]],
    *,
    continue_on_error: bool,
) -> list[TileWorkResult]:
    """Run per-tile workers serially or via a thread pool."""
    results: dict[str, TileWorkResult] = {}
    if tile_jobs == 1 or len(tiles) <= 1:
        for tile in tiles:
            try:
                result, metrics = worker(tile)
                results[tile] = TileWorkResult(tile, result, metrics, None)
            except Exception as exc:
                if not continue_on_error:
                    raise
                results[tile] = TileWorkResult(tile, None, None, str(exc))
        return [results[tile] for tile in tiles]
    with ThreadPoolExecutor(max_workers=tile_jobs) as executor:
        future_map = {executor.submit(worker, tile): tile for tile in tiles}
        for future, tile in future_map.items():
            try:
                result, metrics = future.result()
                results[tile] = TileWorkResult(tile, result, metrics, None)
            except Exception as exc:
                if not continue_on_error:
                    raise
                results[tile] = TileWorkResult(tile, None, None, str(exc))
    return [results[tile] for tile in tiles]


def _apply_aoi_mask(tile_path: Path, shapes: list[dict[str, object]], nodata: float) -> None:
    """Apply an AOI mask to a tile, setting masked pixels to nodata."""
    with rasterio.open(tile_path, "r+") as dataset:
        data = dataset.read(1)
        mask = geometry_mask(
            shapes,
            out_shape=data.shape,
            transform=dataset.transform,
            invert=False,
        )
        if not mask.any():
            return
        data = data.copy()
        data[mask] = nodata
        dataset.write(data, 1)


def _merge_sources_for_tile(
    sources: Iterable[Path],
    tile: str,
    output_path: Path,
    *,
    resolution: tuple[float, float] | None,
    resampling: Resampling,
    dst_nodata: float | None,
    compression: str | None = None,
) -> TileResult:
    """Merge sources for a tile directly into a GeoTIFF."""
    source_paths = list(sources)
    if not source_paths:
        raise ValueError("At least one DEM source is required.")
    with ExitStack() as stack:
        datasets = [stack.enter_context(rasterio.open(path)) for path in source_paths]
        base = datasets[0]
        if base.crs is None:
            raise ValueError("Source DEM CRS is required for tiling.")
        bounds = tile_bounds_in_crs(tile, base.crs)
        res = resolution or (abs(base.res[0]), abs(base.res[1]))
        nodata = dst_nodata if dst_nodata is not None else base.nodata
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dst_kwds = {"driver": "GTiff", "nodata": nodata}
        if compression:
            dst_kwds["compress"] = compression
        merge(
            datasets,
            bounds=bounds,
            res=res,
            nodata=nodata,
            resampling=resampling,
            dst_path=output_path,
            dst_kwds=dst_kwds,
        )
    return TileResult(
        tile=tile,
        path=output_path,
        bounds=tile_bounds(tile),
        resolution=res,
        nodata=nodata,
    )


def _combine_stack_tiles(tile_paths: Iterable[Path], nodata: float | None) -> np.ndarray:
    """Blend stack layer tiles by overwriting nodata gaps."""
    combined: np.ndarray | None = None
    for tile_path in tile_paths:
        with rasterio.open(tile_path) as dataset:
            data = dataset.read(1)
            layer_nodata = nodata if nodata is not None else dataset.nodata
            mask = _nodata_mask(data, layer_nodata)
            if combined is None:
                combined = data
            else:
                combined = np.where(~mask, data, combined)
    if combined is None:
        raise ValueError("No stack layers to combine.")
    return combined


def _coverage_stats(path: Path, nodata_override: float | None) -> tuple[int, int, float]:
    """Return total pixels, nodata count, and coverage ratio for a tile."""
    with rasterio.open(path) as dataset:
        nodata = nodata_override if nodata_override is not None else dataset.nodata
        total = dataset.width * dataset.height
        if total == 0:
            return 0, 0, 1.0
        use_data = False
        if nodata is None:
            use_data = False
        elif np.isnan(nodata):
            use_data = True
        elif dataset.nodata is None or dataset.nodata != nodata:
            use_data = True
        nodata_pixels = 0
        if use_data:
            for _, window in dataset.block_windows(1):
                data = dataset.read(1, window=window)
                mask = _nodata_mask(data, nodata)
                nodata_pixels += int(mask.sum())
        else:
            for _, window in dataset.block_windows(1):
                mask = dataset.read_masks(1, window=window)
                nodata_pixels += int((mask == 0).sum())
    coverage = 1.0 if total == 0 else (total - nodata_pixels) / total
    return total, nodata_pixels, coverage


def _apply_fill_strategy(
    tile_path: Path,
    *,
    strategy: str,
    nodata: float | None,
    fill_value: float,
    fallback_path: Path | None,
) -> FillResult | None:
    """Apply a fill strategy to a tile and return fill details."""
    if strategy == "none":
        return None
    with rasterio.open(tile_path, "r+") as dataset:
        band = dataset.read(1)
        nodata_value = nodata if nodata is not None else dataset.nodata
        if strategy == "constant":
            result = fill_with_constant(band, nodata=nodata_value, fill_value=fill_value)
        elif strategy == "interpolate":
            result = fill_with_interpolation(band, nodata=nodata_value)
        elif strategy == "fallback":
            if fallback_path is None:
                raise ValueError("Fallback fill requires fallback DEMs.")
            with rasterio.open(fallback_path) as fallback:
                fallback_band = fallback.read(1)
            result = fill_with_fallback(
                band,
                fallback_band,
                nodata=nodata_value,
            )
        else:
            raise ValueError(f"Unknown fill strategy: {strategy}")
        dataset.write(result.filled, 1)
        return result


def _prepare_sources(
    dem_paths: Iterable[Path],
    *,
    work_dir: Path,
    target_crs: str,
    resampling: str,
    resolution: tuple[float, float] | None,
    dst_nodata: float | None,
    label: str,
) -> tuple[Path, ...]:
    """Warp sources to a common CRS/resolution and return paths."""
    warped_paths = []
    for index, path in enumerate(dem_paths):
        info: DemInfo = inspect_dem(path)
        if info.crs is None:
            raise ValueError(f"DEM is missing CRS: {path}")
        if info.crs != target_crs:
            warped_path = work_dir / "warp" / label / f"dem_{index}.tif"
            warp_dem(
                path,
                warped_path,
                target_crs,
                resolution=resolution,
                resampling=_resampling(resampling),
                dst_nodata=dst_nodata,
            )
            warped_paths.append(warped_path)
        else:
            warped_paths.append(path)
    return tuple(warped_paths)


def normalize_for_tiles(
    dem_paths: Iterable[Path],
    tiles: Iterable[str],
    work_dir: Path,
    *,
    target_crs: str,
    resampling: str = "bilinear",
    dst_nodata: float | None = None,
    resolution: tuple[float, float] | None = None,
    fill_strategy: str = "none",
    fill_value: float = 0.0,
    fallback_dem_paths: Iterable[Path] | None = None,
    backend_profile: BackendProfile | None = None,
    tile_jobs: int = 1,
    continue_on_error: bool = False,
    coverage_metrics: bool = True,
    mosaic_strategy: str = "full",
    compression: str | None = None,
) -> NormalizationResult:
    """Normalize DEM inputs into per-tile artifacts."""
    dem_paths = tuple(dem_paths)
    tiles = list(tiles)
    if not dem_paths:
        raise ValueError("At least one DEM path is required.")
    tile_jobs = _coerce_tile_jobs(tile_jobs, len(tiles))
    if mosaic_strategy not in {"full", "per-tile", "vrt"}:
        raise ValueError("mosaic_strategy must be 'full', 'per-tile', or 'vrt'")

    effective_nodata = dst_nodata
    if backend_profile:
        if normalize_crs(target_crs) != normalize_crs(backend_profile.crs):
            raise ValueError("Target CRS must match backend profile.")
        if backend_profile.nodata is not None:
            effective_nodata = backend_profile.nodata

    warped_paths = _prepare_sources(
        dem_paths,
        work_dir=work_dir,
        target_crs=target_crs,
        resampling=resampling,
        resolution=resolution,
        dst_nodata=effective_nodata,
        label="primary",
    )

    primary_sources = warped_paths
    if len(warped_paths) > 1 and mosaic_strategy in {"full", "vrt"}:
        suffix = "vrt" if mosaic_strategy == "vrt" else "tif"
        mosaic_path = work_dir / "mosaic" / f"mosaic.{suffix}"
        build_mosaic(
            warped_paths,
            mosaic_path,
            driver="VRT" if mosaic_strategy == "vrt" else "GTiff",
            compression=compression,
        )
    else:
        if not warped_paths:
            raise ValueError("No DEM sources available after warping.")
        mosaic_path = warped_paths[0]

    fallback_paths: tuple[Path, ...] = tuple(fallback_dem_paths or [])
    fallback_sources: tuple[Path, ...] = ()
    fallback_mosaic: Path | None = None
    if fill_strategy == "fallback":
        if not fallback_paths:
            raise ValueError("Fallback fill requires fallback DEMs.")
        fallback_warped = _prepare_sources(
            fallback_paths,
            work_dir=work_dir,
            target_crs=target_crs,
            resampling=resampling,
            resolution=resolution,
            dst_nodata=effective_nodata,
            label="fallback",
        )
        fallback_sources = fallback_warped
        if len(fallback_warped) > 1 and mosaic_strategy in {"full", "vrt"}:
            suffix = "vrt" if mosaic_strategy == "vrt" else "tif"
            fallback_mosaic = work_dir / "mosaic" / f"fallback.{suffix}"
            build_mosaic(
                fallback_warped,
                fallback_mosaic,
                driver="VRT" if mosaic_strategy == "vrt" else "GTiff",
                compression=compression,
            )
        elif len(fallback_warped) == 1:
            fallback_mosaic = fallback_warped[0]

    tile_results = []
    tile_dir = work_dir / "tiles"
    coverage: dict[str, CoverageMetrics] = {}

    def process_tile(tile: str) -> tuple[TileResult, CoverageMetrics]:
        """Normalize a single tile and return coverage metrics."""
        start_time = perf_counter()
        output_path = tile_dir / tile / f"{tile}.tif"
        if mosaic_strategy == "per-tile" and len(primary_sources) > 1:
            tile_result = _merge_sources_for_tile(
                primary_sources,
                tile,
                output_path,
                resolution=resolution,
                resampling=_resampling(resampling),
                dst_nodata=effective_nodata,
                compression=compression,
            )
        else:
            tile_result = write_tile_dem(
                mosaic_path,
                tile,
                output_path,
                resolution=resolution,
                resampling=_resampling(resampling),
                dst_nodata=effective_nodata,
                compression=compression,
            )
        total_pixels = 0
        nodata_before = 0
        coverage_before = 1.0
        if coverage_metrics or fill_strategy == "fallback":
            total_pixels, nodata_before, coverage_before = _coverage_stats(
                output_path, effective_nodata
            )

        fallback_tile = None
        if fill_strategy == "fallback" and nodata_before > 0:
            fallback_tile = work_dir / "fallback_tiles" / tile / f"{tile}.tif"
            if fallback_mosaic is not None:
                write_tile_dem(
                    fallback_mosaic,
                    tile,
                    fallback_tile,
                    resolution=resolution,
                    resampling=_resampling(resampling),
                    dst_nodata=effective_nodata,
                    compression=compression,
                )
            elif fallback_sources:
                if mosaic_strategy == "per-tile" and len(fallback_sources) > 1:
                    _merge_sources_for_tile(
                        fallback_sources,
                        tile,
                        fallback_tile,
                        resolution=resolution,
                        resampling=_resampling(resampling),
                        dst_nodata=effective_nodata,
                        compression=compression,
                    )
                else:
                    if not fallback_sources:
                        raise ValueError("Fallback sources missing for fill.")
                    fallback_first = next(iter(fallback_sources))
                    write_tile_dem(
                        fallback_first,
                        tile,
                        fallback_tile,
                        resolution=resolution,
                        resampling=_resampling(resampling),
                        dst_nodata=effective_nodata,
                        compression=compression,
                    )

        fill_result = None
        if fill_strategy != "fallback" or nodata_before > 0:
            fill_result = _apply_fill_strategy(
                output_path,
                strategy=fill_strategy,
                nodata=effective_nodata,
                fill_value=fill_value,
                fallback_path=fallback_tile,
            )

        filled_pixels = fill_result.filled_pixels if fill_result else 0
        if coverage_metrics:
            nodata_after = fill_result.nodata_pixels_after if fill_result else nodata_before
            total_after = total_pixels
            coverage_after = coverage_before if total_pixels else 1.0
            if total_pixels:
                coverage_after = (total_pixels - nodata_after) / total_pixels
        else:
            total_after = total_pixels
            nodata_after = max(0, nodata_before - filled_pixels)
            coverage_after = coverage_before if total_pixels else 1.0

        if backend_profile and backend_profile.require_full_coverage and nodata_after > 0:
            raise ValueError("Backend profile requires void-free DEMs.")
        metrics = CoverageMetrics(
            total_pixels=total_pixels or total_after,
            nodata_pixels_before=nodata_before,
            nodata_pixels_after=nodata_after,
            coverage_before=coverage_before,
            coverage_after=coverage_after,
            filled_pixels=filled_pixels,
            strategy=fill_strategy,
            normalize_seconds=perf_counter() - start_time,
        )
        result = TileResult(
            tile=tile,
            path=output_path,
            bounds=tile_result.bounds,
            resolution=tile_result.resolution,
            nodata=tile_result.nodata,
        )
        return result, metrics

    errors: dict[str, str] = {}
    for work in _run_tile_jobs(
        tiles,
        tile_jobs,
        process_tile,
        continue_on_error=continue_on_error,
    ):
        if work.error:
            errors[work.tile] = work.error
            continue
        if work.result is None or work.metrics is None:
            errors[work.tile] = "Tile normalization failed"
            continue
        tile_results.append(work.result)
        if coverage_metrics:
            coverage[work.result.tile] = work.metrics

    return NormalizationResult(
        sources=dem_paths,
        target_crs=target_crs,
        mosaic_path=mosaic_path,
        tile_results=tuple(tile_results),
        coverage=coverage,
        errors=errors,
    )


def normalize_stack_for_tiles(
    stack: DemStack,
    tiles: Iterable[str],
    work_dir: Path,
    *,
    target_crs: str,
    resampling: str = "bilinear",
    dst_nodata: float | None = None,
    resolution: tuple[float, float] | None = None,
    fill_strategy: str = "none",
    fill_value: float = 0.0,
    fallback_dem_paths: Iterable[Path] | None = None,
    backend_profile: BackendProfile | None = None,
    tile_jobs: int = 1,
    continue_on_error: bool = False,
    coverage_metrics: bool = True,
    mosaic_strategy: str = "full",
    compression: str | None = None,
) -> NormalizationResult:
    """Normalize a DEM stack into per-tile artifacts."""
    layers = stack.sorted_layers()
    if not layers:
        raise ValueError("DEM stack requires at least one layer.")
    tiles = list(tiles)
    tile_jobs = _coerce_tile_jobs(tile_jobs, len(tiles))
    if mosaic_strategy not in {"full", "per-tile", "vrt"}:
        raise ValueError("mosaic_strategy must be 'full', 'per-tile', or 'vrt'")

    effective_nodata = dst_nodata
    if backend_profile:
        if normalize_crs(target_crs) != normalize_crs(backend_profile.crs):
            raise ValueError("Target CRS must match backend profile.")
        if backend_profile.nodata is not None:
            effective_nodata = backend_profile.nodata
    if effective_nodata is None:
        for layer in layers:
            if layer.nodata is not None:
                effective_nodata = layer.nodata
                break

    warped_layers: list[tuple[int, Path, float | None, Path | None]] = []
    for index, layer in enumerate(layers):
        layer_nodata = layer.nodata if layer.nodata is not None else effective_nodata
        warped = _prepare_sources(
            [layer.path],
            work_dir=work_dir,
            target_crs=target_crs,
            resampling=resampling,
            resolution=resolution,
            dst_nodata=layer_nodata,
            label=f"stack_{index}",
        )
        warped_layers.append((layer.priority, warped[0], layer_nodata, layer.aoi))

    fallback_paths: tuple[Path, ...] = tuple(fallback_dem_paths or [])
    fallback_sources: tuple[Path, ...] = ()
    fallback_mosaic: Path | None = None
    if fill_strategy == "fallback":
        if not fallback_paths:
            raise ValueError("Fallback fill requires fallback DEMs.")
        fallback_warped = _prepare_sources(
            fallback_paths,
            work_dir=work_dir,
            target_crs=target_crs,
            resampling=resampling,
            resolution=resolution,
            dst_nodata=effective_nodata,
            label="fallback",
        )
        fallback_sources = fallback_warped
        if len(fallback_warped) > 1 and mosaic_strategy in {"full", "vrt"}:
            suffix = "vrt" if mosaic_strategy == "vrt" else "tif"
            fallback_mosaic = work_dir / "mosaic" / f"fallback.{suffix}"
            build_mosaic(
                fallback_warped,
                fallback_mosaic,
                driver="VRT" if mosaic_strategy == "vrt" else "GTiff",
                compression=compression,
            )
        elif len(fallback_warped) == 1:
            fallback_mosaic = fallback_warped[0]

    aoi_shapes: dict[Path, list[dict[str, object]]] = {}
    for _, _, _, aoi in warped_layers:
        if aoi and aoi not in aoi_shapes:
            aoi_shapes[aoi] = load_aoi_shapes(aoi)

    tile_results = []
    tile_dir = work_dir / "tiles"
    coverage: dict[str, CoverageMetrics] = {}

    def process_tile(tile: str) -> tuple[TileResult, CoverageMetrics]:
        """Normalize a stack tile and return coverage metrics."""
        start_time = perf_counter()
        layer_tile_paths: list[Path] = []
        tile_result: TileResult | None = None
        for index, (_, layer_path, layer_nodata, aoi) in enumerate(warped_layers):
            tile_path = work_dir / "stack_layers" / f"layer_{index}" / tile / f"{tile}.tif"
            tile_result = write_tile_dem(
                layer_path,
                tile,
                tile_path,
                resolution=resolution,
                resampling=_resampling(resampling),
                dst_nodata=layer_nodata,
                compression=compression,
            )
            if aoi:
                if layer_nodata is None:
                    raise ValueError("AOI mask requires a nodata value.")
                _apply_aoi_mask(tile_path, aoi_shapes[aoi], layer_nodata)
            layer_tile_paths.append(tile_path)

        if tile_result is None:
            raise ValueError(f"No stack layers generated for tile {tile}")

        output_path = tile_dir / tile / f"{tile}.tif"
        combined = _combine_stack_tiles(layer_tile_paths, effective_nodata)
        with rasterio.open(layer_tile_paths[0]) as template:
            meta = template.meta.copy()
        if effective_nodata is not None:
            meta["nodata"] = effective_nodata
        if compression:
            meta["compress"] = compression
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **meta) as dest:
            dest.write(combined, 1)

        total_pixels = 0
        nodata_before = 0
        coverage_before = 1.0
        if coverage_metrics or fill_strategy == "fallback":
            total_pixels, nodata_before, coverage_before = _coverage_stats(
                output_path, effective_nodata
            )

        fallback_tile = None
        if fill_strategy == "fallback" and nodata_before > 0:
            fallback_tile = work_dir / "fallback_tiles" / tile / f"{tile}.tif"
            if fallback_mosaic is not None:
                write_tile_dem(
                    fallback_mosaic,
                    tile,
                    fallback_tile,
                    resolution=resolution,
                    resampling=_resampling(resampling),
                    dst_nodata=effective_nodata,
                    compression=compression,
                )
            elif fallback_sources:
                if mosaic_strategy == "per-tile" and len(fallback_sources) > 1:
                    _merge_sources_for_tile(
                        fallback_sources,
                        tile,
                        fallback_tile,
                        resolution=resolution,
                        resampling=_resampling(resampling),
                        dst_nodata=effective_nodata,
                        compression=compression,
                    )
                else:
                    if not fallback_sources:
                        raise ValueError("Fallback sources missing for fill.")
                    fallback_first = next(iter(fallback_sources))
                    write_tile_dem(
                        fallback_first,
                        tile,
                        fallback_tile,
                        resolution=resolution,
                        resampling=_resampling(resampling),
                        dst_nodata=effective_nodata,
                        compression=compression,
                    )

        fill_result = None
        if fill_strategy != "fallback" or nodata_before > 0:
            fill_result = _apply_fill_strategy(
                output_path,
                strategy=fill_strategy,
                nodata=effective_nodata,
                fill_value=fill_value,
                fallback_path=fallback_tile,
            )

        filled_pixels = fill_result.filled_pixels if fill_result else 0
        if coverage_metrics:
            nodata_after = fill_result.nodata_pixels_after if fill_result else nodata_before
            total_after = total_pixels
            coverage_after = coverage_before if total_pixels else 1.0
            if total_pixels:
                coverage_after = (total_pixels - nodata_after) / total_pixels
        else:
            total_after = total_pixels
            nodata_after = max(0, nodata_before - filled_pixels)
            coverage_after = coverage_before if total_pixels else 1.0

        if backend_profile and backend_profile.require_full_coverage and nodata_after > 0:
            raise ValueError("Backend profile requires void-free DEMs.")
        metrics = CoverageMetrics(
            total_pixels=total_pixels or total_after,
            nodata_pixels_before=nodata_before,
            nodata_pixels_after=nodata_after,
            coverage_before=coverage_before,
            coverage_after=coverage_after,
            filled_pixels=filled_pixels,
            strategy=fill_strategy,
            normalize_seconds=perf_counter() - start_time,
        )
        result = TileResult(
            tile=tile,
            path=output_path,
            bounds=tile_result.bounds,
            resolution=tile_result.resolution,
            nodata=tile_result.nodata,
        )
        return result, metrics

    errors: dict[str, str] = {}
    for work in _run_tile_jobs(
        tiles,
        tile_jobs,
        process_tile,
        continue_on_error=continue_on_error,
    ):
        if work.error:
            errors[work.tile] = work.error
            continue
        if work.result is None or work.metrics is None:
            errors[work.tile] = "Tile normalization failed"
            continue
        tile_results.append(work.result)
        if coverage_metrics:
            coverage[work.result.tile] = work.metrics

    mosaic_path = warped_layers[0][1]
    return NormalizationResult(
        sources=tuple(layer.path for layer in layers),
        target_crs=target_crs,
        mosaic_path=mosaic_path,
        tile_results=tuple(tile_results),
        coverage=coverage,
        errors=errors,
    )
