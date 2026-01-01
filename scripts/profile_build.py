"""Profile a dem2dsf build using cProfile."""

from __future__ import annotations

import argparse
import cProfile
import os
import pstats
from pathlib import Path

from dem2dsf import cli


def _tile_slug(tiles: list[str]) -> str:
    """Return a filename-safe slug based on tiles."""
    if not tiles:
        return "build"
    if len(tiles) == 1:
        return tiles[0].replace("+", "p").replace("-", "m")
    return "multi"


def _add_optional_arg(args: list[str], flag: str, value: str | None) -> None:
    """Append a flag/value pair when a value exists."""
    if value is not None:
        args.extend([flag, str(value)])


def _build_cli_args(
    args: argparse.Namespace, metrics_path: Path
) -> list[str]:
    """Translate script arguments into dem2dsf CLI args."""
    cli_args: list[str] = ["build"]
    for dem in args.dem or []:
        cli_args.extend(["--dem", dem])
    if args.dem_stack:
        cli_args.extend(["--dem-stack", args.dem_stack])
    for tile in args.tile or []:
        cli_args.extend(["--tile", tile])
    _add_optional_arg(cli_args, "--quality", args.quality)
    _add_optional_arg(cli_args, "--density", args.density)
    _add_optional_arg(cli_args, "--output", args.output)
    if args.runner:
        cli_args.extend(["--runner", *args.runner])
    if args.dsftool:
        cli_args.extend(["--dsftool", *args.dsftool])
    _add_optional_arg(cli_args, "--global-scenery", args.global_scenery)
    if args.enrich_xp12:
        cli_args.append("--enrich-xp12")
    _add_optional_arg(cli_args, "--target-crs", args.target_crs)
    _add_optional_arg(cli_args, "--target-resolution", args.target_resolution)
    _add_optional_arg(cli_args, "--resampling", args.resampling)
    _add_optional_arg(cli_args, "--dst-nodata", args.dst_nodata)
    _add_optional_arg(cli_args, "--fill-strategy", args.fill_strategy)
    _add_optional_arg(cli_args, "--fill-value", args.fill_value)
    for fallback_dem in args.fallback_dem or []:
        cli_args.extend(["--fallback-dem", fallback_dem])
    if args.skip_normalize:
        cli_args.append("--skip-normalize")
    _add_optional_arg(cli_args, "--warn-triangles", args.warn_triangles)
    _add_optional_arg(cli_args, "--max-triangles", args.max_triangles)
    if args.allow_triangle_overage:
        cli_args.append("--allow-triangle-overage")
    if args.autoortho:
        cli_args.append("--autoortho")
    if args.dry_run:
        cli_args.append("--dry-run")

    cli_args.append("--profile")
    cli_args.extend(["--metrics-json", str(metrics_path)])
    return cli_args


def main() -> int:
    """CLI entrypoint for profiling builds."""
    parser = argparse.ArgumentParser(description="Profile a dem2dsf build.")
    parser.add_argument("--dem", action="append", help="DEM input path.")
    parser.add_argument("--dem-stack", help="DEM stack JSON path.")
    parser.add_argument("--tile", action="append", help="Tile name like +DD+DDD.")
    parser.add_argument("--quality", default="compat", help="Quality mode.")
    parser.add_argument("--density", default="medium", help="Density preset.")
    parser.add_argument("--output", default="build", help="Build output dir.")
    parser.add_argument("--runner", nargs="+", help="Ortho4XP runner command.")
    parser.add_argument("--dsftool", nargs="+", help="DSFTool command.")
    parser.add_argument("--global-scenery", help="Global Scenery path.")
    parser.add_argument(
        "--enrich-xp12", action="store_true", help="Enable XP12 enrichment."
    )
    parser.add_argument("--target-crs", help="Override target CRS.")
    parser.add_argument(
        "--target-resolution",
        type=float,
        help="Target resolution in meters (approx for EPSG:4326).",
    )
    parser.add_argument(
        "--resampling",
        choices=("nearest", "bilinear", "cubic", "average"),
        default="bilinear",
        help="Resampling method.",
    )
    parser.add_argument("--dst-nodata", type=float, help="Override nodata value.")
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
    parser.add_argument(
        "--skip-normalize",
        action="store_true",
        help="Skip DEM normalization.",
    )
    parser.add_argument("--warn-triangles", type=int, help="Warn threshold.")
    parser.add_argument("--max-triangles", type=int, help="Error threshold.")
    parser.add_argument(
        "--allow-triangle-overage",
        action="store_true",
        help="Allow triangle overage.",
    )
    parser.add_argument(
        "--autoortho", action="store_true", help="Enable AutoOrtho mode."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry run only.")
    parser.add_argument(
        "--profile-dir",
        default=os.environ.get("DEM2DSF_PROFILE_DIR", "profiles"),
        help="Directory for profiler outputs.",
    )
    parser.add_argument(
        "--metrics-json",
        help="Optional metrics JSON output path override.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Write a text summary of top functions.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=40,
        help="Number of functions to include in the summary.",
    )
    args = parser.parse_args()

    if not args.tile:
        parser.error("--tile is required")
    if not args.dem and not args.dem_stack:
        parser.error("--dem or --dem-stack is required")

    profile_dir = Path(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    slug = _tile_slug(args.tile or [])
    metrics_path = (
        Path(args.metrics_json)
        if args.metrics_json
        else profile_dir / f"build_{slug}.metrics.json"
    )
    stats_path = profile_dir / f"build_{slug}.pstats"

    cli_args = _build_cli_args(args, metrics_path)
    profiler = cProfile.Profile()
    exit_code = profiler.runcall(lambda: cli.main(cli_args))
    profiler.dump_stats(str(stats_path))

    if args.summary:
        summary_path = profile_dir / f"build_{slug}.txt"
        with summary_path.open("w", encoding="utf-8") as handle:
            stats = pstats.Stats(profiler, stream=handle)
            stats.sort_stats("cumulative")
            stats.print_stats(args.top)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
