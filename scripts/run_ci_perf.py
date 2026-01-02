"""Run lightweight performance checks for CI."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import numpy as np
import rasterio
from rasterio.transform import from_bounds


def _write_demo_dem(path: Path) -> None:
    """Write a tiny GeoTIFF DEM for benchmark use."""
    data = np.array([[100.0, 101.0], [102.0, 103.0]], dtype="float32")
    transform = from_bounds(8.0, 47.0, 9.0, 48.0, 2, 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=-9999.0,
    ) as dest:
        dest.write(data, 1)


def _prepare_publish_dir(root: Path, tile: str) -> Path:
    """Create a minimal build directory for publish benchmarks."""
    dsf_dir = root / "build" / "Earth nav data" / tile
    dsf_dir.mkdir(parents=True, exist_ok=True)
    (dsf_dir / f"{tile}.dsf").write_text("dsf", encoding="utf-8")
    return dsf_dir.parents[2]


def _run_script(script: Path, args: list[str]) -> None:
    """Run a benchmark script and raise on failure."""
    command = [sys.executable, str(script), *args]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}")


def _max_seconds(csv_path: Path) -> float:
    """Return the maximum seconds value from a benchmark CSV."""
    max_seconds = 0.0
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                seconds = float(row.get("seconds", 0.0))
            except (TypeError, ValueError):
                seconds = 0.0
            max_seconds = max(max_seconds, seconds)
    return max_seconds


def _load_baseline(path: Path) -> dict[str, float] | None:
    """Load a baseline summary from JSON, if available."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _delta_percent(current: float, baseline: float | None) -> float | None:
    """Return percent delta from baseline, or None when unavailable."""
    if baseline is None or baseline <= 0:
        return None
    return (current - baseline) / baseline * 100.0


def _write_trend(
    output_dir: Path,
    summary: dict[str, float | str | int],
    baseline_path: Path,
    baseline: dict[str, float],
) -> dict[str, object]:
    """Write trend summary JSON/Markdown and return the payload."""
    normalize_base = float(baseline.get("normalize_seconds", 0.0))
    publish_base = float(baseline.get("publish_seconds", 0.0))
    normalize_current = float(summary["normalize_seconds"])
    publish_current = float(summary["publish_seconds"])
    trend = {
        "baseline_path": str(baseline_path),
        "baseline": baseline,
        "current": summary,
        "delta_seconds": {
            "normalize": round(normalize_current - normalize_base, 6),
            "publish": round(publish_current - publish_base, 6),
        },
        "delta_percent": {
            "normalize": _delta_percent(normalize_current, normalize_base),
            "publish": _delta_percent(publish_current, publish_base),
        },
    }
    normalize_pct = trend["delta_percent"]["normalize"]
    publish_pct = trend["delta_percent"]["publish"]
    normalize_pct_text = f"{normalize_pct:.2f}" if normalize_pct is not None else "n/a"
    publish_pct_text = f"{publish_pct:.2f}" if publish_pct is not None else "n/a"
    trend_path = output_dir / "trend.json"
    trend_path.write_text(json.dumps(trend, indent=2), encoding="utf-8")
    trend_md = [
        "# Perf Trend",
        "",
        f"Baseline: `{baseline_path}`",
        "",
        "| Metric | Baseline (s) | Current (s) | Delta (s) | Delta (%) |",
        "| --- | --- | --- | --- | --- |",
        f"| normalize | {normalize_base:.6f} | {normalize_current:.6f} | "
        f"{trend['delta_seconds']['normalize']:.6f} | "
        f"{normalize_pct_text} |",
        f"| publish | {publish_base:.6f} | {publish_current:.6f} | "
        f"{trend['delta_seconds']['publish']:.6f} | "
        f"{publish_pct_text} |",
        "",
    ]
    (output_dir / "trend.md").write_text("\n".join(trend_md), encoding="utf-8")
    return trend


def main() -> int:
    """CLI entrypoint for CI performance checks."""
    parser = argparse.ArgumentParser(description="Run lightweight performance benchmarks for CI.")
    parser.add_argument(
        "--output-dir",
        default="perf_ci",
        help="Directory for performance outputs.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of benchmark runs.",
    )
    parser.add_argument(
        "--tile",
        default="+47+008",
        help="Tile to use for synthetic benchmarks.",
    )
    parser.add_argument(
        "--normalize-max-seconds",
        type=float,
        default=5.0,
        help="Max allowed seconds for normalization.",
    )
    parser.add_argument(
        "--publish-max-seconds",
        type=float,
        default=5.0,
        help="Max allowed seconds for publish.",
    )
    repo_root = Path(__file__).resolve().parents[1]
    default_baseline = repo_root / "perf_baselines" / "ci_baseline.json"
    parser.add_argument(
        "--baseline",
        default=str(default_baseline),
        help="Optional baseline JSON for trend reporting.",
    )
    parser.add_argument(
        "--baseline-max-regression-pct",
        type=float,
        default=None,
        help="Fail if percent regression exceeds this threshold.",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Emit warnings instead of failing on threshold regressions.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write the current summary to the baseline path.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    dem_path = data_dir / "demo_dem.tif"

    _write_demo_dem(dem_path)
    build_dir = _prepare_publish_dir(output_dir, args.tile)

    script_dir = Path(__file__).resolve().parent
    normalize_dir = output_dir / "normalize"
    publish_dir = output_dir / "publish"

    _run_script(
        script_dir / "benchmark_normalize.py",
        [
            "--dem",
            str(dem_path),
            "--tile",
            args.tile,
            "--runs",
            str(args.runs),
            "--output-dir",
            str(normalize_dir),
        ],
    )
    _run_script(
        script_dir / "benchmark_publish.py",
        [
            "--build-dir",
            str(build_dir),
            "--runs",
            str(args.runs),
            "--output-dir",
            str(publish_dir),
        ],
    )

    normalize_csv = normalize_dir / "normalize.csv"
    publish_csv = publish_dir / "publish.csv"
    normalize_seconds = _max_seconds(normalize_csv)
    publish_seconds = _max_seconds(publish_csv)

    summary = {
        "tile": args.tile,
        "runs": args.runs,
        "normalize_seconds": round(normalize_seconds, 6),
        "publish_seconds": round(publish_seconds, 6),
        "normalize_max_seconds": args.normalize_max_seconds,
        "publish_max_seconds": args.publish_max_seconds,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    failures = []
    if normalize_seconds > args.normalize_max_seconds:
        failures.append(f"normalize {normalize_seconds:.3f}s > {args.normalize_max_seconds:.3f}s")
    if publish_seconds > args.publish_max_seconds:
        failures.append(f"publish {publish_seconds:.3f}s > {args.publish_max_seconds:.3f}s")

    baseline_path = Path(args.baseline) if args.baseline else None
    if baseline_path:
        baseline = _load_baseline(baseline_path)
        if baseline:
            trend = _write_trend(output_dir, summary, baseline_path, baseline)
            max_regression = args.baseline_max_regression_pct
            if max_regression is not None:
                deltas = cast(dict[str, float | None], trend["delta_percent"])
                for key, delta in deltas.items():
                    if delta is None:
                        continue
                    if delta > max_regression:
                        failures.append(f"{key} regression {delta:.2f}% > {max_regression:.2f}%")
        elif baseline_path.exists():
            print(f"Baseline file invalid: {baseline_path}")
    if args.write_baseline and baseline_path:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if failures:
        header = "Perf warnings (non-fatal):" if args.warn_only else "Perf thresholds exceeded:"
        print(header)
        for failure in failures:
            print(f"- {failure}")
        if not args.warn_only:
            return 1

    print("Perf summary:")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
