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
- Use `--skip-coverage-metrics` to reduce normalization I/O when coverage checks are not needed.
- Prefer `--mosaic-strategy per-tile` or `--mosaic-strategy vrt` to reduce full-mosaic memory pressure.
- Use `--normalized-compression lzw` or `deflate` to reduce disk usage (with extra CPU cost).
- Enable `--cache-sha256` when validating cache correctness matters more than speed.

## GDAL/rasterio knobs
- `GDAL_CACHEMAX`: increase cache size for large warps (MB).
- `GDAL_NUM_THREADS=ALL_CPUS`: enables multi-threaded warps when supported.
- `CPL_TMPDIR`: put temp files on a fast disk.
- GDAL/rasterio threading can be sensitive; if you see crashes or hangs, drop `--tile-jobs`
  to 1-4 or use `--tile-jobs 0` for conservative auto sizing. Process-based parallelism
  for heavy raster steps is a future enhancement.

## Backend-specific tips
- Ortho4XP: run with `--batch` in the runner for headless mode (ignored if the upstream script does not support flags).

## Gotchas
- Over-aggressive resolution can hit triangle caps and slow validation steps.
- Excessive mosaicking in a single run can cause memory spikes; split tiles if needed.
- Build reports include size/triangle estimates; treat large-build warnings as a sign to split runs.
