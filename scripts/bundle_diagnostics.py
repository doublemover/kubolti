"""Bundle build reports and performance metrics into a zip archive."""

from __future__ import annotations

import argparse
from pathlib import Path

from dem2dsf.diagnostics import bundle_diagnostics, default_profile_dir


def main() -> int:
    """CLI entrypoint for bundling diagnostics."""
    parser = argparse.ArgumentParser(
        description="Bundle dem2dsf build reports and metrics."
    )
    parser.add_argument(
        "--build-dir",
        default="build",
        help="Build output directory (default: build).",
    )
    parser.add_argument(
        "--output",
        help="Optional zip output path (default: <build-dir>/diagnostics_<ts>.zip).",
    )
    parser.add_argument(
        "--metrics",
        action="append",
        help="Additional metrics JSON path(s) to include.",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(default_profile_dir()),
        help="Profile directory to include (default: profiles).",
    )
    parser.add_argument(
        "--no-profiles",
        action="store_true",
        help="Skip including profile outputs.",
    )
    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Skip including runner logs.",
    )
    args = parser.parse_args()

    build_dir = Path(args.build_dir)
    metrics = [Path(value).expanduser() for value in (args.metrics or [])]
    profile_dir = Path(args.profile_dir).expanduser()
    output_path = Path(args.output) if args.output else None

    try:
        bundle_path = bundle_diagnostics(
            build_dir,
            output_path=output_path,
            metrics=metrics,
            profile_dir=profile_dir,
            include_profiles=not args.no_profiles,
            include_logs=not args.no_logs,
        )
    except FileNotFoundError as exc:
        print(str(exc))
        return 2

    if bundle_path is None:
        print("No diagnostics files found to bundle.")
        return 1

    print(f"Wrote diagnostics bundle to {bundle_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
