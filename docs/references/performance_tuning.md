# Performance Tuning Notes

Source: DEM2DSF spec + implementation (internal reference).

## Why it matters
Large mosaics and high-resolution tiles are expensive. These tips help keep build times and memory usage in check.

## Key points
- Choose an appropriate `--target-resolution`; higher resolution increases triangles and build time.
- Prefer `bilinear` or `average` resampling for speed; `cubic` is slower but smoother.
- Use DEM stacks sparingly: large numbers of layers increase IO and blending costs.
- Use `--triangle-warn`/`--triangle-max` guardrails to avoid surprise meshing blow-ups.
- Keep outputs on fast storage; avoid network drives for `normalized/` and `build/` directories.

## GDAL/rasterio knobs
- `GDAL_CACHEMAX`: increase cache size for large warps (MB).
- `GDAL_NUM_THREADS=ALL_CPUS`: enables multi-threaded warps when supported.
- `CPL_TMPDIR`: put temp files on a fast disk.

## Backend-specific tips
- Ortho4XP: run with `--batch` in the runner for headless mode (ignored if the upstream script does not support flags).

## Gotchas
- Over-aggressive resolution can hit triangle caps and slow validation steps.
- Excessive mosaicking in a single run can cause memory spikes; split tiles if needed.
