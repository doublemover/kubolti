"""Benchmark publish and compression throughput."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from time import perf_counter

from dem2dsf.publish import find_sevenzip, publish_build


def main() -> int:
    """CLI entrypoint for publish benchmarks."""
    parser = argparse.ArgumentParser(
        description="Benchmark publish and compression performance."
    )
    parser.add_argument(
        "--build-dir",
        required=True,
        help="Build output directory to package.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs.",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmarks/publish",
        help="Base output directory.",
    )
    parser.add_argument(
        "--csv-path",
        help="Optional CSV output path override.",
    )
    parser.add_argument(
        "--dsf-7z",
        action="store_true",
        help="Enable 7z compression for DSF files.",
    )
    parser.add_argument(
        "--sevenzip-path",
        help="Path to the 7z executable.",
    )
    parser.add_argument(
        "--allow-missing-7z",
        action="store_true",
        help="Proceed without 7z if not available.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = Path(args.csv_path) if args.csv_path else output_dir / "publish.csv"

    sevenzip_path = Path(args.sevenzip_path) if args.sevenzip_path else None
    if args.dsf_7z and sevenzip_path is None:
        detected = find_sevenzip()
        if detected:
            sevenzip_path = detected
        elif not args.allow_missing_7z:
            print("7z not found; pass --sevenzip-path or --allow-missing-7z.")
            return 2

    rows: list[dict[str, object]] = []
    for run in range(1, args.runs + 1):
        run_dir = output_dir / f"run_{run:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        output_zip = run_dir / "build.zip"
        start = perf_counter()
        result = publish_build(
            Path(args.build_dir),
            output_zip,
            dsf_7z=args.dsf_7z,
            sevenzip_path=sevenzip_path,
            allow_missing_sevenzip=args.allow_missing_7z,
        )
        elapsed = perf_counter() - start
        output_size = output_zip.stat().st_size if output_zip.exists() else 0
        rows.append(
            {
                "run": run,
                "seconds": round(elapsed, 6),
                "bytes": output_size,
                "zip_path": str(result.get("zip_path", output_zip)),
            }
        )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["run", "seconds", "bytes", "zip_path"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
