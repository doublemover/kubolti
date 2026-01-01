"""Benchmark DEM normalization throughput."""

from __future__ import annotations

import argparse
import csv
import math
import shutil
import tracemalloc
from pathlib import Path
from time import perf_counter

from dem2dsf.dem.adapter import profile_for_backend
from dem2dsf.dem.pipeline import normalize_for_tiles, normalize_stack_for_tiles
from dem2dsf.dem.stack import load_dem_stack
from dem2dsf.dem.tiling import tile_bounds


def _resolve_output_dir(path_value: str) -> Path:
    """Resolve the benchmark output directory."""
    output_dir = Path(path_value)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _resolution_from_options(
    target_resolution: float | None,
    tiles: list[str],
    target_crs: str,
) -> tuple[float, float] | None:
    """Derive a resolution tuple using the build heuristics."""
    if target_resolution is None:
        return None
    resolution_m = float(target_resolution)
    if resolution_m <= 0:
        raise ValueError("Target resolution must be positive.")
    if target_crs.upper() in {"EPSG:4326", "EPSG:4258"}:
        meters_per_deg_lat = 111_320.0
        latitudes = []
        for tile in tiles:
            _, min_lat, _, max_lat = tile_bounds(tile)
            latitudes.append((min_lat + max_lat) / 2.0)
        avg_lat = sum(latitudes) / len(latitudes) if latitudes else 0.0
        meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(avg_lat))
        if meters_per_deg_lon <= 0:
            meters_per_deg_lon = meters_per_deg_lat
        return (resolution_m / meters_per_deg_lon, resolution_m / meters_per_deg_lat)
    return (resolution_m, resolution_m)


def main() -> int:
    """CLI entrypoint for normalization benchmarks."""
    parser = argparse.ArgumentParser(
        description="Benchmark normalization performance."
    )
    parser.add_argument("--dem", action="append", help="DEM input path.")
    parser.add_argument("--dem-stack", help="DEM stack JSON path.")
    parser.add_argument("--tile", action="append", help="Tile name like +DD+DDD.")
    parser.add_argument("--backend", default="ortho4xp", help="Backend profile.")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs.")
    parser.add_argument(
        "--output-dir",
        default="benchmarks/normalize",
        help="Base output directory.",
    )
    parser.add_argument(
        "--csv-path",
        help="Optional CSV output path override.",
    )
    parser.add_argument("--target-crs", default="EPSG:4326", help="Target CRS.")
    parser.add_argument(
        "--target-resolution",
        type=float,
        default=None,
        help="Target resolution in meters.",
    )
    parser.add_argument(
        "--resampling",
        choices=("nearest", "bilinear", "cubic", "average"),
        default="bilinear",
        help="Resampling method.",
    )
    parser.add_argument("--dst-nodata", type=float, default=None, help="Nodata.")
    parser.add_argument(
        "--fill-strategy",
        choices=("none", "constant", "interpolate", "fallback"),
        default="none",
        help="Fill strategy.",
    )
    parser.add_argument("--fill-value", type=float, default=0.0, help="Fill value.")
    parser.add_argument(
        "--fallback-dem", action="append", help="Fallback DEM path(s)."
    )
    args = parser.parse_args()

    if not args.tile:
        parser.error("--tile is required")
    if not args.dem and not args.dem_stack:
        parser.error("--dem or --dem-stack is required")

    output_dir = _resolve_output_dir(args.output_dir)
    csv_path = Path(args.csv_path) if args.csv_path else output_dir / "normalize.csv"
    backend_profile = profile_for_backend(args.backend)

    rows: list[dict[str, object]] = []
    resolution = _resolution_from_options(
        args.target_resolution, args.tile, args.target_crs
    )
    for run in range(1, args.runs + 1):
        run_dir = output_dir / f"run_{run:02d}"
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        tracemalloc.start()
        start = perf_counter()
        if args.dem_stack:
            stack = load_dem_stack(Path(args.dem_stack))
            normalization = normalize_stack_for_tiles(
                stack,
                args.tile,
                run_dir / "normalized",
                target_crs=args.target_crs,
                resampling=args.resampling,
                dst_nodata=args.dst_nodata,
                resolution=resolution,
                fill_strategy=args.fill_strategy,
                fill_value=args.fill_value,
                fallback_dem_paths=[
                    Path(path) for path in args.fallback_dem or []
                ],
                backend_profile=backend_profile,
            )
        else:
            normalization = normalize_for_tiles(
                [Path(path) for path in args.dem or []],
                args.tile,
                run_dir / "normalized",
                target_crs=args.target_crs,
                resampling=args.resampling,
                dst_nodata=args.dst_nodata,
                resolution=resolution,
                fill_strategy=args.fill_strategy,
                fill_value=args.fill_value,
                fallback_dem_paths=[
                    Path(path) for path in args.fallback_dem or []
                ],
                backend_profile=backend_profile,
            )
        elapsed = perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        for tile_result in normalization.tile_results:
            rows.append(
                {
                    "run": run,
                    "tile": tile_result.tile,
                    "seconds": round(elapsed, 6),
                    "peak_mb": round(peak / (1024 * 1024), 3),
                    "output_dir": str(run_dir),
                    "mosaic_path": str(normalization.mosaic_path),
                }
            )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "run",
                "tile",
                "seconds",
                "peak_mb",
                "output_dir",
                "mosaic_path",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
