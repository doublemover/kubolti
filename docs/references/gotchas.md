# Common Gotchas

Source: DEM2DSF spec + implementation (internal reference).

## Why it matters
Most failed builds are caused by subtle CRS, nodata, or tool path issues. This list captures the problems we see most often.

## Key points
- CRS axis order: always normalize to EPSG:4326 and be explicit about axis order when reprojecting.
- Tile bounds: DEM tiles must match exact 1x1 degree bounds for the target tile.
- Nodata handling: missing nodata values lead to voids or unexpected fills. Always set nodata explicitly.
- Ortho4XP output naming: output tiles live under `Custom Scenery/zOrtho4XP_<tile>`.
- Ortho4XP DEM buckets: custom DEM files belong under `Elevation_data/+LL+LLL/` and use N/S/E/W filenames.
- Windows paths: quote paths with spaces; pass `--runner` as a full command.
- 7-Zip availability: publishing with `--dsf-7z` requires 7z or `--allow-missing-7z`.
- XP12 raster checks: `--quality xp12-enhanced` treats missing soundscape/season rasters as errors.

## Gotchas
- Ortho4XP Python version mismatches can silently fail; prefer an explicit `--python` in the runner (often 3.10 for numpy < 2 builds).
- Global Scenery path must point at the root (not just a single tile) for XP12 enrichment.
