# Performance Profiling and Benchmarking

These scripts provide repeatable, cross-platform measurements without external tooling.

## Profile a full build
Runs `dem2dsf build` under `cProfile` and captures timing metrics.

```bash
python scripts/profile_build.py \
  --dem data/dem.tif \
  --tile +47+008 \
  --output build \
  --runner python scripts/ortho4xp_runner.py \
  --summary
```

Outputs (default under `profiles/` or `DEM2DSF_PROFILE_DIR`):
- `build_<tile>.pstats`
- `build_<tile>.metrics.json`
- Optional `build_<tile>.txt` when `--summary` is set

## Benchmark normalization
Measures normalization speed for a DEM or DEM stack.

```bash
python scripts/benchmark_normalize.py \
  --dem data/dem.tif \
  --tile +47+008 \
  --runs 5
```

Output: `benchmarks/normalize/normalize.csv` with run timings and peak memory.

## Benchmark publish
Measures publish + compression overhead.

```bash
python scripts/benchmark_publish.py \
  --build-dir build \
  --runs 3 \
  --dsf-7z \
  --sevenzip-path /path/to/7z
```

Output: `benchmarks/publish/publish.csv` with duration and output size.

## Build report hooks
- `dem2dsf build --profile` adds a `performance` block to `build_report.json`.  
- `--metrics-json <path>` writes the same metrics to a standalone JSON file.    
- `DEM2DSF_PROFILE_DIR` controls the default metrics output directory.

## Bundle diagnostics
Collect build reports, runner logs, and metrics into a shareable zip:

```bash
python scripts/bundle_diagnostics.py \
  --build-dir build \
  --profile-dir profiles
```

Use `--metrics <path>` to add extra JSON metrics and `--no-logs`/`--no-profiles`
to skip optional sections.

## CI tracking
CI runs `scripts/run_ci_perf.py` on a tiny synthetic DEM and uploads the
`perf_ci/` artifacts (CSV + summary JSON). The thresholds are intentionally
loose and warn-only to catch major regressions, not micro-optimizations.

Baseline trends:
- Default baseline: `perf_baselines/ci_baseline.json` in the repo.
- `run_ci_perf.py` writes `perf_ci/trend.json` and `perf_ci/trend.md` when a
  baseline is present.
- Update the baseline after intentional changes:
  `python scripts/run_ci_perf.py --output-dir perf_ci --write-baseline`
- `summary.json` now includes `python_version`, `python_implementation`,        
  `platform`, `machine`, and `processor` metadata for baseline context.
