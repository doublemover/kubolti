"""Command-line interface for dem2dsf."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from dem2dsf import __version__
from dem2dsf.build import run_build
from dem2dsf.density import DENSITY_PRESETS
from dem2dsf.doctor import run_doctor
from dem2dsf.logging_utils import LogOptions, configure_logging
from dem2dsf.overlay import run_overlay
from dem2dsf.patch import run_patch
from dem2dsf.presets import (
    default_user_presets_path,
    format_preset,
    get_preset,
    list_presets,
    load_presets_file,
    load_user_presets,
    preset_as_dict,
    serialize_presets,
    write_user_presets,
)
from dem2dsf.publish import find_sevenzip, publish_build
from dem2dsf.scenery import scan_custom_scenery
from dem2dsf.tools.config import load_tool_paths, ortho_root_from_paths
from dem2dsf.tools.ortho4xp import (
    CACHE_CATEGORIES,
    find_tile_cache_entries,
    purge_tile_cache_entries,
)
from dem2dsf.wizard import run_wizard

RESAMPLING_CHOICES = ("nearest", "bilinear", "cubic", "average")
LOGGER = logging.getLogger("dem2dsf.cli")


@dataclass(frozen=True)
class BuildOptions:
    """Structured build options derived from CLI arguments."""

    quality: str
    density: str
    autoortho: bool
    runner: list[str] | None
    dsftool: list[str] | None
    global_scenery: str | None
    enrich_xp12: bool
    target_crs: str | None
    target_resolution: float | None
    resampling: str
    dst_nodata: float | None
    fill_strategy: str
    fill_value: float
    fallback_dem_paths: list[str] | None
    tile_jobs: int
    normalize: bool
    triangle_warn: int | None
    triangle_max: int | None
    allow_triangle_overage: bool
    continue_on_error: bool
    coverage_min: float | None
    coverage_hard_fail: bool
    coverage_metrics: bool
    mosaic_strategy: str
    runner_timeout: float | None
    runner_retries: int
    runner_stream_logs: bool
    dsftool_timeout: float | None
    dsftool_retries: int
    bundle_diagnostics: bool
    dry_run: bool
    dem_stack_path: str | None
    profile: bool
    metrics_json: str | None
    provenance_level: str
    stable_metadata: bool
    pinned_versions_path: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "quality": self.quality,
            "autoortho": self.autoortho,
            "density": self.density,
            "runner": self.runner,
            "dsftool": self.dsftool,
            "global_scenery": self.global_scenery,
            "enrich_xp12": self.enrich_xp12,
            "target_crs": self.target_crs,
            "target_resolution": self.target_resolution,
            "resampling": self.resampling,
            "dst_nodata": self.dst_nodata,
            "fill_strategy": self.fill_strategy,
            "fill_value": self.fill_value,
            "fallback_dem_paths": self.fallback_dem_paths,
            "tile_jobs": self.tile_jobs,
            "normalize": self.normalize,
            "triangle_warn": self.triangle_warn,
            "triangle_max": self.triangle_max,
            "allow_triangle_overage": self.allow_triangle_overage,
            "continue_on_error": self.continue_on_error,
            "coverage_min": self.coverage_min,
            "coverage_hard_fail": self.coverage_hard_fail,
            "coverage_metrics": self.coverage_metrics,
            "mosaic_strategy": self.mosaic_strategy,
            "runner_timeout": self.runner_timeout,
            "runner_retries": self.runner_retries,
            "runner_stream_logs": self.runner_stream_logs,
            "dsftool_timeout": self.dsftool_timeout,
            "dsftool_retries": self.dsftool_retries,
            "bundle_diagnostics": self.bundle_diagnostics,
            "dry_run": self.dry_run,
            "dem_stack_path": self.dem_stack_path,
            "profile": self.profile,
            "metrics_json": self.metrics_json,
            "provenance_level": self.provenance_level,
            "stable_metadata": self.stable_metadata,
            "pinned_versions_path": self.pinned_versions_path,
        }


def _build_options_from_args(
    args: argparse.Namespace,
    *,
    autoortho: bool | None = None,
    runner: list[str] | None = None,
    dry_run: bool | None = None,
) -> BuildOptions:
    """Normalize CLI args into a BuildOptions payload."""
    resolved_autoortho = autoortho
    if resolved_autoortho is None:
        resolved_autoortho = bool(getattr(args, "autoortho", False))
    return BuildOptions(
        quality=args.quality,
        density=args.density,
        autoortho=resolved_autoortho,
        runner=runner if runner is not None else getattr(args, "runner", None),
        dsftool=getattr(args, "dsftool", None),
        global_scenery=getattr(args, "global_scenery", None),
        enrich_xp12=bool(getattr(args, "enrich_xp12", False)),
        target_crs=getattr(args, "target_crs", None),
        target_resolution=getattr(args, "target_resolution", None),
        resampling=args.resampling,
        dst_nodata=getattr(args, "dst_nodata", None),
        fill_strategy=args.fill_strategy,
        fill_value=float(getattr(args, "fill_value", 0.0) or 0.0),
        fallback_dem_paths=getattr(args, "fallback_dem", None),
        tile_jobs=int(getattr(args, "tile_jobs", 1) or 1),
        normalize=not bool(getattr(args, "skip_normalize", False)),
        triangle_warn=getattr(args, "warn_triangles", None),
        triangle_max=getattr(args, "max_triangles", None),
        allow_triangle_overage=bool(getattr(args, "allow_triangle_overage", False)),
        continue_on_error=bool(getattr(args, "continue_on_error", False)),
        coverage_min=getattr(args, "min_coverage", None),
        coverage_hard_fail=bool(getattr(args, "coverage_hard_fail", False)),
        coverage_metrics=not bool(getattr(args, "skip_coverage_metrics", False)),
        mosaic_strategy=getattr(args, "mosaic_strategy", "full"),
        runner_timeout=getattr(args, "runner_timeout", None),
        runner_retries=int(getattr(args, "runner_retries", 0) or 0),
        runner_stream_logs=bool(getattr(args, "runner_stream_logs", False)),
        dsftool_timeout=getattr(args, "dsftool_timeout", None),
        dsftool_retries=int(getattr(args, "dsftool_retries", 0) or 0),
        bundle_diagnostics=bool(getattr(args, "bundle_diagnostics", False)),
        dry_run=dry_run if dry_run is not None else bool(getattr(args, "dry_run", False)),
        dem_stack_path=getattr(args, "dem_stack", None),
        profile=bool(getattr(args, "profile", False)),
        metrics_json=getattr(args, "metrics_json", None),
        provenance_level=getattr(args, "provenance_level", "basic"),
        stable_metadata=bool(getattr(args, "stable_metadata", False)),
        pinned_versions_path=getattr(args, "pinned_versions", None),
    )


def _add_build_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the build subcommand and its arguments."""
    build = subparsers.add_parser("build", help="Build DSF tiles from DEM inputs.")
    build.add_argument("--dem", action="append", help="Path to a DEM input file.")
    build.add_argument(
        "--dem-stack",
        help="Path to a JSON DEM stack definition.",
    )
    build.add_argument("--tile", action="append", help="Tile name like +DD+DDD.")
    build.add_argument(
        "--quality",
        choices=("compat", "xp12-enhanced"),
        default="compat",
        help="Raster quality mode for XP12.",
    )
    build.add_argument(
        "--density",
        choices=tuple(DENSITY_PRESETS.keys()),
        default="medium",
        help="Mesh density preset.",
    )
    build.add_argument(
        "--output",
        default="build",
        help="Output directory for build artifacts.",
    )
    build.add_argument(
        "--runner",
        nargs="+",
        help="Command to invoke the Ortho4XP runner.",
    )
    build.add_argument(
        "--dsftool",
        nargs="+",
        help="Command to invoke DSFTool for DSF validation.",
    )
    build.add_argument(
        "--global-scenery",
        help="Path to a Global Scenery folder for XP12 raster checks.",
    )
    build.add_argument(
        "--enrich-xp12",
        action="store_true",
        help="Attempt to copy XP12 rasters from Global Scenery.",
    )
    build.add_argument(
        "--target-crs",
        default=None,
        help="Override target CRS for normalization.",
    )
    build.add_argument(
        "--target-resolution",
        type=float,
        default=None,
        help="Target resolution in meters (approx for EPSG:4326).",
    )
    build.add_argument(
        "--resampling",
        choices=RESAMPLING_CHOICES,
        default="bilinear",
        help="Resampling method for normalization.",
    )
    build.add_argument(
        "--dst-nodata",
        type=float,
        default=None,
        help="Override nodata value for normalized tiles.",
    )
    build.add_argument(
        "--fill-strategy",
        choices=("none", "constant", "interpolate", "fallback"),
        default="none",
        help="Strategy for filling nodata gaps in normalized tiles.",
    )
    build.add_argument(
        "--fill-value",
        type=float,
        default=0.0,
        help="Fill value for constant strategy.",
    )
    build.add_argument(
        "--fallback-dem",
        action="append",
        help="Fallback DEM path(s) for fallback fill strategy.",
    )
    build.add_argument(
        "--tile-jobs",
        "--jobs",
        type=int,
        default=1,
        help="Parallel tile workers for normalization (default: 1).",
    )
    build.add_argument(
        "--mosaic-strategy",
        choices=("full", "per-tile"),
        default="full",
        help="Mosaic strategy for multiple DEMs (default: full).",
    )
    build.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue other tiles when a tile fails.",
    )
    build.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        help="Minimum coverage ratio (0-1) before fill warnings.",
    )
    build.add_argument(
        "--coverage-hard-fail",
        action="store_true",
        help="Fail tiles that fall below the minimum coverage threshold.",
    )
    build.add_argument(
        "--skip-coverage-metrics",
        action="store_true",
        help="Skip coverage metrics collection for normalization.",
    )
    build.add_argument(
        "--runner-timeout",
        type=float,
        default=None,
        help="Timeout in seconds for the Ortho4XP runner.",
    )
    build.add_argument(
        "--runner-retries",
        type=int,
        default=0,
        help="Retry failed Ortho4XP runner invocations.",
    )
    build.add_argument(
        "--runner-stream-logs",
        action="store_true",
        help="Stream runner output to log files instead of capturing.",
    )
    build.add_argument(
        "--dsftool-timeout",
        type=float,
        default=None,
        help="Timeout in seconds for DSFTool invocations.",
    )
    build.add_argument(
        "--dsftool-retries",
        type=int,
        default=0,
        help="Retry failed DSFTool invocations.",
    )
    build.add_argument(
        "--skip-normalize",
        action="store_true",
        help="Skip DEM normalization and pass inputs directly to the backend.",
    )
    build.add_argument(
        "--warn-triangles",
        type=int,
        default=None,
        help="Warn when triangle estimates exceed this count.",
    )
    build.add_argument(
        "--max-triangles",
        type=int,
        default=None,
        help="Error when triangle estimates exceed this count.",
    )
    build.add_argument(
        "--allow-triangle-overage",
        action="store_true",
        help="Allow triangle estimates above the max threshold.",
    )
    build.add_argument("--dry-run", action="store_true", help="Write plan/report only.")
    build.add_argument("--autoortho", action="store_true", help="Enable AutoOrtho mode.")
    build.add_argument(
        "--profile",
        action="store_true",
        help="Capture timing metrics in the build report.",
    )
    build.add_argument(
        "--metrics-json",
        help="Optional path to write performance metrics JSON.",
    )
    build.add_argument(
        "--bundle-diagnostics",
        action="store_true",
        help="Bundle diagnostics artifacts after the build completes.",
    )
    build.add_argument(
        "--provenance-level",
        choices=("basic", "strict"),
        default="basic",
        help="Provenance detail level (default: basic).",
    )
    build.add_argument(
        "--stable-metadata",
        action="store_true",
        help="Omit volatile metadata fields like created_at from plan/report.",
    )
    build.add_argument(
        "--pinned-versions",
        help="Override pinned versions config (defaults to package or DEM2DSF_PINNED_VERSIONS).",
    )


def _add_wizard_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the interactive wizard subcommand."""
    wizard = subparsers.add_parser("wizard", help="Run the interactive build wizard.")
    wizard.add_argument("--dem", action="append", help="Path to a DEM input file.")
    wizard.add_argument(
        "--dem-stack",
        help="Path to a JSON DEM stack definition.",
    )
    wizard.add_argument("--tile", action="append", help="Tile name like +DD+DDD.")
    wizard.add_argument(
        "--quality",
        choices=("compat", "xp12-enhanced"),
        default="compat",
        help="Raster quality mode for XP12.",
    )
    wizard.add_argument(
        "--density",
        choices=tuple(DENSITY_PRESETS.keys()),
        default="medium",
        help="Mesh density preset.",
    )
    wizard.add_argument(
        "--output",
        default="build",
        help="Output directory for build artifacts.",
    )
    wizard.add_argument(
        "--runner",
        nargs="+",
        help="Command to invoke the Ortho4XP runner.",
    )
    wizard.add_argument(
        "--dsftool",
        nargs="+",
        help="Command to invoke DSFTool for DSF validation.",
    )
    wizard.add_argument(
        "--global-scenery",
        help="Path to a Global Scenery folder for XP12 raster checks.",
    )
    wizard.add_argument(
        "--enrich-xp12",
        action="store_true",
        help="Attempt to copy XP12 rasters from Global Scenery.",
    )
    wizard.add_argument(
        "--target-crs",
        default=None,
        help="Override target CRS for normalization.",
    )
    wizard.add_argument(
        "--target-resolution",
        type=float,
        default=None,
        help="Target resolution in meters (approx for EPSG:4326).",
    )
    wizard.add_argument(
        "--resampling",
        choices=RESAMPLING_CHOICES,
        default="bilinear",
        help="Resampling method for normalization.",
    )
    wizard.add_argument(
        "--dst-nodata",
        type=float,
        default=None,
        help="Override nodata value for normalized tiles.",
    )
    wizard.add_argument(
        "--fill-strategy",
        choices=("none", "constant", "interpolate", "fallback"),
        default="none",
        help="Strategy for filling nodata gaps in normalized tiles.",
    )
    wizard.add_argument(
        "--fill-value",
        type=float,
        default=0.0,
        help="Fill value for constant strategy.",
    )
    wizard.add_argument(
        "--fallback-dem",
        action="append",
        help="Fallback DEM path(s) for fallback fill strategy.",
    )
    wizard.add_argument(
        "--tile-jobs",
        "--jobs",
        type=int,
        default=1,
        help="Parallel tile workers for normalization (default: 1).",
    )
    wizard.add_argument(
        "--mosaic-strategy",
        choices=("full", "per-tile"),
        default="full",
        help="Mosaic strategy for multiple DEMs (default: full).",
    )
    wizard.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue other tiles when a tile fails.",
    )
    wizard.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        help="Minimum coverage ratio (0-1) before fill warnings.",
    )
    wizard.add_argument(
        "--coverage-hard-fail",
        action="store_true",
        help="Fail tiles that fall below the minimum coverage threshold.",
    )
    wizard.add_argument(
        "--skip-coverage-metrics",
        action="store_true",
        help="Skip coverage metrics collection for normalization.",
    )
    wizard.add_argument(
        "--runner-timeout",
        type=float,
        default=None,
        help="Timeout in seconds for the Ortho4XP runner.",
    )
    wizard.add_argument(
        "--runner-retries",
        type=int,
        default=0,
        help="Retry failed Ortho4XP runner invocations.",
    )
    wizard.add_argument(
        "--runner-stream-logs",
        action="store_true",
        help="Stream runner output to log files instead of capturing.",
    )
    wizard.add_argument(
        "--dsftool-timeout",
        type=float,
        default=None,
        help="Timeout in seconds for DSFTool invocations.",
    )
    wizard.add_argument(
        "--dsftool-retries",
        type=int,
        default=0,
        help="Retry failed DSFTool invocations.",
    )
    wizard.add_argument(
        "--skip-normalize",
        action="store_true",
        help="Skip DEM normalization and pass inputs directly to the backend.",
    )
    wizard.add_argument(
        "--warn-triangles",
        type=int,
        default=None,
        help="Warn when triangle estimates exceed this count.",
    )
    wizard.add_argument(
        "--max-triangles",
        type=int,
        default=None,
        help="Error when triangle estimates exceed this count.",
    )
    wizard.add_argument(
        "--allow-triangle-overage",
        action="store_true",
        help="Allow triangle estimates above the max threshold.",
    )
    wizard.add_argument("--autoortho", action="store_true", help="Enable AutoOrtho mode.")
    wizard.add_argument("--defaults", action="store_true", help="Skip prompts.")
    wizard.add_argument("--dry-run", action="store_true", help="Write plan/report only.")
    wizard.add_argument(
        "--profile",
        action="store_true",
        help="Capture timing metrics in the build report.",
    )
    wizard.add_argument(
        "--metrics-json",
        help="Optional path to write performance metrics JSON.",
    )
    wizard.add_argument(
        "--bundle-diagnostics",
        action="store_true",
        help="Bundle diagnostics artifacts after the build completes.",
    )
    wizard.add_argument(
        "--provenance-level",
        choices=("basic", "strict"),
        default="basic",
        help="Provenance detail level (default: basic).",
    )
    wizard.add_argument(
        "--stable-metadata",
        action="store_true",
        help="Omit volatile metadata fields like created_at from plan/report.",
    )
    wizard.add_argument(
        "--pinned-versions",
        help="Override pinned versions config (defaults to package or DEM2DSF_PINNED_VERSIONS).",
    )


def _add_doctor_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the doctor subcommand."""
    doctor = subparsers.add_parser("doctor", help="Check external dependencies and environment.")
    doctor.add_argument(
        "--runner",
        nargs="+",
        help="Command used to invoke the Ortho4XP runner.",
    )
    doctor.add_argument(
        "--dsftool",
        nargs="+",
        help="Command used to invoke DSFTool.",
    )


def _add_autoortho_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the AutoOrtho preset subcommand."""
    auto = subparsers.add_parser("autoortho", help="AutoOrtho preset build mode (Ortho4XP runner).")
    auto.add_argument("--dem", action="append", help="Path to a DEM input file.")
    auto.add_argument(
        "--dem-stack",
        help="Path to a JSON DEM stack definition.",
    )
    auto.add_argument("--tile", action="append", help="Tile name like +DD+DDD.")
    auto.add_argument(
        "--ortho-root",
        help="Path to the Ortho4XP root folder.",
    )
    auto.add_argument(
        "--output",
        default="build",
        help="Output directory for build artifacts.",
    )
    auto.add_argument(
        "--quality",
        choices=("compat", "xp12-enhanced"),
        default="compat",
        help="Raster quality mode for XP12.",
    )
    auto.add_argument(
        "--density",
        choices=tuple(DENSITY_PRESETS.keys()),
        default="medium",
        help="Mesh density preset.",
    )
    auto.add_argument(
        "--target-crs",
        default=None,
        help="Override target CRS for normalization.",
    )
    auto.add_argument(
        "--target-resolution",
        type=float,
        default=None,
        help="Target resolution in meters (approx for EPSG:4326).",
    )
    auto.add_argument(
        "--resampling",
        choices=RESAMPLING_CHOICES,
        default="bilinear",
        help="Resampling method for normalization.",
    )
    auto.add_argument(
        "--dst-nodata",
        type=float,
        default=None,
        help="Override nodata value for normalized tiles.",
    )
    auto.add_argument(
        "--fill-strategy",
        choices=("none", "constant", "interpolate", "fallback"),
        default="none",
        help="Strategy for filling nodata gaps in normalized tiles.",
    )
    auto.add_argument(
        "--fill-value",
        type=float,
        default=0.0,
        help="Fill value for constant strategy.",
    )
    auto.add_argument(
        "--fallback-dem",
        action="append",
        help="Fallback DEM path(s) for fallback fill strategy.",
    )
    auto.add_argument(
        "--tile-jobs",
        "--jobs",
        type=int,
        default=1,
        help="Parallel tile workers for normalization (default: 1).",
    )
    auto.add_argument(
        "--mosaic-strategy",
        choices=("full", "per-tile"),
        default="full",
        help="Mosaic strategy for multiple DEMs (default: full).",
    )
    auto.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue other tiles when a tile fails.",
    )
    auto.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        help="Minimum coverage ratio (0-1) before fill warnings.",
    )
    auto.add_argument(
        "--coverage-hard-fail",
        action="store_true",
        help="Fail tiles that fall below the minimum coverage threshold.",
    )
    auto.add_argument(
        "--skip-coverage-metrics",
        action="store_true",
        help="Skip coverage metrics collection for normalization.",
    )
    auto.add_argument(
        "--skip-normalize",
        action="store_true",
        help="Skip DEM normalization and pass inputs directly to the backend.",
    )
    auto.add_argument(
        "--dsftool",
        nargs="+",
        help="Command to invoke DSFTool for DSF validation.",
    )
    auto.add_argument(
        "--global-scenery",
        help="Path to a Global Scenery folder for XP12 raster checks.",
    )
    auto.add_argument(
        "--enrich-xp12",
        action="store_true",
        help="Attempt to copy XP12 rasters from Global Scenery.",
    )
    auto.add_argument(
        "--warn-triangles",
        type=int,
        default=None,
        help="Warn when triangle estimates exceed this count.",
    )
    auto.add_argument(
        "--max-triangles",
        type=int,
        default=None,
        help="Error when triangle estimates exceed this count.",
    )
    auto.add_argument(
        "--allow-triangle-overage",
        action="store_true",
        help="Allow triangle estimates above the max threshold.",
    )
    auto.add_argument(
        "--batch",
        action="store_true",
        help="Pass --batch to Ortho4XP.",
    )
    auto.add_argument(
        "--ortho-python",
        help="Python executable for Ortho4XP.",
    )
    auto.add_argument(
        "--runner-timeout",
        type=float,
        default=None,
        help="Timeout in seconds for the Ortho4XP runner.",
    )
    auto.add_argument(
        "--runner-retries",
        type=int,
        default=0,
        help="Retry failed Ortho4XP runner invocations.",
    )
    auto.add_argument(
        "--runner-stream-logs",
        action="store_true",
        help="Stream runner output to log files instead of capturing.",
    )
    auto.add_argument(
        "--profile",
        action="store_true",
        help="Capture timing metrics in the build report.",
    )
    auto.add_argument(
        "--metrics-json",
        help="Optional path to write performance metrics JSON.",
    )
    auto.add_argument(
        "--bundle-diagnostics",
        action="store_true",
        help="Bundle diagnostics artifacts after the build completes.",
    )
    auto.add_argument(
        "--provenance-level",
        choices=("basic", "strict"),
        default="basic",
        help="Provenance detail level (default: basic).",
    )
    auto.add_argument(
        "--stable-metadata",
        action="store_true",
        help="Omit volatile metadata fields like created_at from plan/report.",
    )
    auto.add_argument(
        "--pinned-versions",
        help="Override pinned versions config (defaults to package or DEM2DSF_PINNED_VERSIONS).",
    )
    auto.add_argument(
        "--dsftool-timeout",
        type=float,
        default=None,
        help="Timeout in seconds for DSFTool invocations.",
    )
    auto.add_argument(
        "--dsftool-retries",
        type=int,
        default=0,
        help="Retry failed DSFTool invocations.",
    )


def _add_overlay_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the overlay generation subcommand."""
    overlay = subparsers.add_parser(
        "overlay",
        help="Generate overlay scenery (drape, plugins).",
    )
    overlay.add_argument(
        "--generator",
        default="drape",
        help="Overlay generator name (default: drape).",
    )
    overlay.add_argument(
        "--build-dir",
        help="Base build directory (required for drape).",
    )
    overlay.add_argument(
        "--output",
        required=True,
        help="Output directory for overlay artifacts.",
    )
    overlay.add_argument(
        "--texture",
        help="Texture path for drape overlays.",
    )
    overlay.add_argument(
        "--texture-name",
        help="Override texture file name when copying.",
    )
    overlay.add_argument(
        "--terrain-glob",
        default="*.ter",
        help="Terrain glob pattern for drape updates.",
    )
    overlay.add_argument(
        "--skip-terrain",
        action="store_true",
        help="Skip copying the terrain directory for copy overlays.",
    )
    overlay.add_argument(
        "--skip-textures",
        action="store_true",
        help="Skip copying the textures directory for copy overlays.",
    )
    overlay.add_argument("--tile", action="append", help="Tile name like +DD+DDD.")
    overlay.add_argument(
        "--plugin",
        action="append",
        help="Path to a Python overlay plugin.",
    )


def _add_patch_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the patch application subcommand."""
    patch = subparsers.add_parser(
        "patch",
        help="Apply localized DEM patches to an existing build.",
    )
    patch.add_argument(
        "--build-dir",
        required=True,
        help="Existing build directory containing build_plan.json.",
    )
    patch.add_argument(
        "--patch",
        required=True,
        help="Path to a JSON patch plan.",
    )
    patch.add_argument(
        "--output",
        help="Optional output directory for patched tiles.",
    )
    patch.add_argument(
        "--runner",
        nargs="+",
        help="Optional Ortho4XP runner override.",
    )
    patch.add_argument(
        "--dsftool",
        nargs="+",
        help="Optional DSFTool override.",
    )
    patch.add_argument(
        "--dry-run",
        action="store_true",
        help="Write patch plan/report only.",
    )


def _add_scan_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the Custom Scenery scan subcommand."""
    scan = subparsers.add_parser("scan", help="Scan Custom Scenery for conflicting tiles.")
    scan.add_argument(
        "--scenery-root",
        required=True,
        help="Custom Scenery root directory.",
    )
    scan.add_argument(
        "--tile",
        action="append",
        help="Limit scan to specific tile(s) like +DD+DDD (repeatable).",
    )
    scan.add_argument(
        "--output",
        help="Optional path to write the scan report JSON.",
    )


def _add_cache_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the Ortho4XP cache inspection subcommands."""
    cache = subparsers.add_parser("cache", help="Inspect or purge Ortho4XP cache entries.")
    cache_sub = cache.add_subparsers(dest="cache_command", required=True)
    cache_list = cache_sub.add_parser("list", help="List cache entries for a tile.")
    cache_list.add_argument(
        "--ortho-root",
        required=True,
        help="Path to the Ortho4XP root directory.",
    )
    cache_list.add_argument("--tile", required=True, help="Tile name like +DD+DDD.")
    cache_list.add_argument(
        "--category",
        action="append",
        choices=CACHE_CATEGORIES,
        help="Limit to specific cache categories (repeatable).",
    )
    cache_list.add_argument(
        "--output",
        help="Optional path to write the cache report JSON.",
    )
    cache_purge = cache_sub.add_parser("purge", help="Delete cache entries for a tile.")
    cache_purge.add_argument(
        "--ortho-root",
        required=True,
        help="Path to the Ortho4XP root directory.",
    )
    cache_purge.add_argument(
        "--tile",
        required=True,
        help="Tile name like +DD+DDD.",
    )
    cache_purge.add_argument(
        "--category",
        action="append",
        choices=CACHE_CATEGORIES,
        help="Limit to specific cache categories (repeatable).",
    )
    cache_purge.add_argument(
        "--confirm",
        action="store_true",
        help="Apply deletions (default is dry-run).",
    )
    cache_purge.add_argument(
        "--output",
        help="Optional path to write the purge report JSON.",
    )


def _add_publish_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the publish subcommand."""
    publish = subparsers.add_parser("publish", help="Package a build directory into a zip archive.")
    publish.add_argument(
        "--build-dir",
        default="build",
        help="Build output directory to package.",
    )
    publish.add_argument(
        "--output",
        default="build.zip",
        help="Zip file output path.",
    )
    publish.add_argument(
        "--dsf-7z",
        action="store_true",
        help="Compress DSF files with 7z before packaging.",
    )
    publish.add_argument(
        "--dsf-7z-backup",
        action="store_true",
        help="Keep .dsf.uncompressed backups when compressing DSFs.",
    )
    publish.add_argument(
        "--sevenzip-path",
        help="Optional path to the 7z executable.",
    )
    publish.add_argument(
        "--allow-missing-7z",
        action="store_true",
        help="Proceed without 7z if it is not available.",
    )


def _add_presets_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the preset library subcommands."""
    presets = subparsers.add_parser("presets", help="List or inspect built-in presets.")
    preset_sub = presets.add_subparsers(dest="preset_command", required=True)
    preset_list = preset_sub.add_parser("list", help="List available presets.")
    preset_list.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    preset_show = preset_sub.add_parser("show", help="Show preset details.")
    preset_show.add_argument("name", help="Preset name.")
    preset_show.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    preset_import = preset_sub.add_parser("import", help="Import user-defined presets from JSON.")
    preset_import.add_argument("path", help="Input JSON file.")
    preset_import.add_argument(
        "--user-path",
        help=(f"User preset file destination. Defaults to {default_user_presets_path()!s}."),
    )
    preset_import.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing user presets instead of merging.",
    )
    preset_export = preset_sub.add_parser("export", help="Export user-defined presets to JSON.")
    preset_export.add_argument(
        "--output",
        default="-",
        help="Output path or '-' for stdout.",
    )
    preset_export.add_argument(
        "--user-path",
        help=(f"User preset file source. Defaults to {default_user_presets_path()!s}."),
    )
    preset_export.add_argument(
        "--include-builtins",
        action="store_true",
        help="Include built-in presets in the export.",
    )


def _add_version_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the version subcommand."""
    subparsers.add_parser("version", help="Print the current version.")


def _add_gui_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the GUI launcher subcommand."""
    subparsers.add_parser("gui", help="Launch the GUI front-end.")


def _default_ortho_runner() -> list[str] | None:
    """Return a command for the bundled Ortho4XP runner if available."""
    if hasattr(sys, "_MEIPASS"):
        candidate = Path(getattr(sys, "_MEIPASS")) / "scripts" / "ortho4xp_runner.py"
        if candidate.exists():
            return [sys.executable, str(candidate)]
    runner = Path(__file__).resolve().parents[2] / "scripts" / "ortho4xp_runner.py"
    if runner.exists():
        return [sys.executable, str(runner)]
    console = shutil.which("dem2dsf-ortho4xp")
    if console:
        return [console]
    return [sys.executable, "-m", "dem2dsf.runners.ortho4xp"]


def _apply_tool_defaults(args: argparse.Namespace) -> None:
    """Populate CLI defaults using the tool discovery config."""
    tool_paths = load_tool_paths()
    if not tool_paths:
        return
    ortho_root = ortho_root_from_paths(tool_paths)
    if hasattr(args, "runner") and args.runner is None and ortho_root:
        runner = _default_ortho_runner()
        if runner:
            args.runner = [*runner, "--ortho-root", str(ortho_root)]
    if hasattr(args, "dsftool") and args.dsftool is None:
        dsftool = tool_paths.get("dsftool")
        if dsftool:
            args.dsftool = [str(dsftool)]
    if hasattr(args, "sevenzip_path") and args.sevenzip_path is None:
        sevenzip = tool_paths.get("7zip") or tool_paths.get("sevenzip")
        if sevenzip:
            args.sevenzip_path = str(sevenzip)
    if hasattr(args, "ortho_root") and args.ortho_root is None and ortho_root:
        args.ortho_root = str(ortho_root)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entrypoint and return an exit code."""
    parser = argparse.ArgumentParser(
        prog="dem2dsf",
        description="DEM2DSF Ortho4XP mesh pipeline",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (repeatable).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce log output to warnings and errors.",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Emit logs as JSON on stderr.",
    )
    parser.add_argument(
        "--log-file",
        help="Optional path for JSON log output.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_build_parser(subparsers)
    _add_wizard_parser(subparsers)
    _add_doctor_parser(subparsers)
    _add_autoortho_parser(subparsers)
    _add_overlay_parser(subparsers)
    _add_patch_parser(subparsers)
    _add_scan_parser(subparsers)
    _add_cache_parser(subparsers)
    _add_publish_parser(subparsers)
    _add_presets_parser(subparsers)
    _add_version_parser(subparsers)
    _add_gui_parser(subparsers)

    args = parser.parse_args(argv)
    log_file_value = getattr(args, "log_file", None)
    log_options = LogOptions(
        verbose=getattr(args, "verbose", 0) or 0,
        quiet=bool(getattr(args, "quiet", False)),
        log_file=Path(log_file_value) if log_file_value else None,
        json_console=bool(getattr(args, "log_json", False)),
    )
    configure_logging(log_options)
    _apply_tool_defaults(args)

    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "gui":
        from dem2dsf.gui import launch_gui

        launch_gui()
        return 0
    if args.command == "build":
        if not args.tile:
            parser.error("--tile is required for build")
        if not args.dem and not args.dem_stack:
            parser.error("--dem or --dem-stack is required for build")
        options = _build_options_from_args(args).as_dict()
        result = run_build(
            dem_paths=[Path(path) for path in (args.dem or [])],
            tiles=args.tile,
            backend_name="ortho4xp",
            output_dir=Path(args.output),
            options=options,
        )
        errors = result.build_report.get("errors", [])
        if errors:
            LOGGER.error("Build completed with errors.")
            for error in errors:
                LOGGER.error("Build error: %s", error)
            return 1
        LOGGER.info("Build plan and report written.")
        return 0
    if args.command == "wizard":
        options = _build_options_from_args(args).as_dict()
        run_wizard(
            dem_paths=args.dem,
            tiles=args.tile,
            output_dir=Path(args.output),
            options=options,
            defaults=args.defaults,
        )
        LOGGER.info("Wizard completed. Build plan and report written.")
        return 0
    if args.command == "doctor":
        results = run_doctor(
            ortho_runner=args.runner,
            dsftool_path=args.dsftool,
        )
        for result in results:
            LOGGER.info("%s: %s - %s", result.name, result.status, result.detail)
        if any(result.status == "error" for result in results):
            return 1
        return 0
    if args.command == "autoortho":
        if not args.tile:
            parser.error("--tile is required for autoortho")
        if not args.dem and not args.dem_stack:
            parser.error("--dem or --dem-stack is required for autoortho")
        if not args.ortho_root:
            parser.error("--ortho-root is required for autoortho")
        runner_cmd = _default_ortho_runner()
        if runner_cmd is None:
            parser.error("AutoOrtho preset requires dem2dsf-ortho4xp runner.")
        runner_cmd = [*runner_cmd, "--ortho-root", args.ortho_root]
        if args.batch:
            runner_cmd.append("--batch")
        if args.ortho_python:
            runner_cmd.extend(["--python", args.ortho_python])
        options = _build_options_from_args(
            args,
            autoortho=True,
            runner=runner_cmd,
            dry_run=False,
        ).as_dict()
        result = run_build(
            dem_paths=[Path(path) for path in (args.dem or [])],
            tiles=args.tile,
            backend_name="ortho4xp",
            output_dir=Path(args.output),
            options=options,
        )
        errors = result.build_report.get("errors", [])
        if errors:
            LOGGER.error("Build completed with errors.")
            for error in errors:
                LOGGER.error("Build error: %s", error)
            return 1
        LOGGER.info("Build plan and report written.")
        return 0
    if args.command == "overlay":
        output_dir = Path(args.output)
        build_dir = Path(args.build_dir) if args.build_dir else None
        options = {
            "texture": args.texture,
            "texture_name": args.texture_name,
            "terrain_glob": args.terrain_glob,
            "include_terrain": not args.skip_terrain,
            "include_textures": not args.skip_textures,
        }
        report = run_overlay(
            build_dir=build_dir,
            output_dir=output_dir,
            generator=args.generator,
            tiles=tuple(args.tile or []),
            options=options,
            plugin_paths=[Path(path) for path in (args.plugin or [])],
        )
        errors = report.get("errors", [])
        if errors:
            LOGGER.error("Overlay completed with errors.")
            for error in errors:
                LOGGER.error("Overlay error: %s", error)
            return 1
        LOGGER.info("Overlay report written to %s", output_dir / "overlay_report.json")
        return 0
    if args.command == "patch":
        overrides = {}
        if args.runner:
            overrides["runner"] = args.runner
        if args.dsftool:
            overrides["dsftool"] = args.dsftool
        output_dir = Path(args.output) if args.output else None
        report = run_patch(
            build_dir=Path(args.build_dir),
            patch_plan_path=Path(args.patch),
            output_dir=output_dir,
            options_override=overrides or None,
            dry_run=args.dry_run,
        )
        LOGGER.info("Patched tiles written to %s", report["output_dir"])
        return 0
    if args.command == "scan":
        report = scan_custom_scenery(
            Path(args.scenery_root),
            tiles=args.tile or None,
        )
        if args.output:
            Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
        conflicts = report.get("conflicts", [])
        LOGGER.info("Found %s conflict(s).", len(conflicts))
        snippet = report.get("suggested_order_snippet")
        if snippet:
            LOGGER.info("Suggested scenery_packs.ini order:")
            for line in snippet:
                LOGGER.info("%s", line)
        return 1 if conflicts else 0
    if args.command == "cache":
        categories = args.category or None
        ortho_root = Path(args.ortho_root)
        if args.cache_command == "list":
            entries = find_tile_cache_entries(
                ortho_root,
                args.tile,
                categories=categories,
            )
            payload = {
                "ortho_root": str(ortho_root),
                "tile": args.tile,
                "entries": {key: [str(path) for path in paths] for key, paths in entries.items()},
            }
            if args.output:
                Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            else:
                print(json.dumps(payload, indent=2))
            return 0
        if args.cache_command == "purge":
            report = purge_tile_cache_entries(
                ortho_root,
                args.tile,
                categories=categories,
                dry_run=not args.confirm,
            )
            if args.output:
                Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
            else:
                print(json.dumps(report, indent=2))
            return 0
    if args.command == "publish":
        sevenzip_path = Path(args.sevenzip_path) if args.sevenzip_path else None
        if args.dsf_7z and sevenzip_path is None:
            detected = find_sevenzip()
            if detected:
                sevenzip_path = detected
            elif sys.stdin.isatty():
                response = input(
                    "7z not found. Enter path or leave blank to continue without 7z: "
                ).strip()
                if response:
                    sevenzip_path = Path(response)
                elif not args.allow_missing_7z:
                    parser.error("7z not found; pass --sevenzip-path or --allow-missing-7z.")
            elif not args.allow_missing_7z:
                parser.error("7z not found; pass --sevenzip-path or --allow-missing-7z.")
        result = publish_build(
            Path(args.build_dir),
            Path(args.output),
            dsf_7z=args.dsf_7z,
            dsf_7z_backup=args.dsf_7z_backup,
            sevenzip_path=sevenzip_path,
            allow_missing_sevenzip=args.allow_missing_7z,
        )
        for warning in result.get("warnings", []):
            LOGGER.warning("Publish warning: %s", warning)
        LOGGER.info("Published build to %s", result["zip_path"])
        return 0
    if args.command == "presets":
        if args.preset_command == "list":
            presets = list_presets()
            if args.format == "json":
                payload = [preset_as_dict(preset) for preset in presets]
                print(json.dumps(payload, indent=2))
            else:
                for preset in presets:
                    print(f"{preset.name}: {preset.summary}")
            return 0
        if args.preset_command == "show":
            preset = get_preset(args.name)
            if not preset:
                LOGGER.error("Unknown preset: %s", args.name)
                return 1
            if args.format == "json":
                print(json.dumps(preset_as_dict(preset), indent=2))
            else:
                print(format_preset(preset))
            return 0
        if args.preset_command == "import":
            source_path = Path(args.path)
            if not source_path.exists():
                LOGGER.error("Preset file not found: %s", source_path)
                return 1
            try:
                incoming = load_presets_file(source_path)
            except (OSError, json.JSONDecodeError) as exc:
                LOGGER.error("Failed to load presets: %s", exc)
                return 1
            dest_path = Path(args.user_path) if args.user_path else default_user_presets_path()
            existing = {} if args.replace else load_user_presets(dest_path)
            merged = dict(existing)
            merged.update(incoming)
            write_user_presets(dest_path, merged)
            LOGGER.info("Imported %s preset(s) to %s", len(incoming), dest_path)
            return 0
        if args.preset_command == "export":
            user_path = Path(args.user_path) if args.user_path else None
            user_presets = load_user_presets(user_path)
            presets_to_export = dict(user_presets)
            if args.include_builtins:
                builtins = {preset.name: preset for preset in list_presets(include_user=False)}
                presets_to_export = dict(builtins)
                presets_to_export.update(user_presets)
            payload = serialize_presets(presets_to_export)
            if args.output == "-" or args.output == "":
                print(json.dumps(payload, indent=2))
            else:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                LOGGER.info(
                    "Exported %s preset(s) to %s",
                    len(presets_to_export),
                    output_path,
                )
            return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
