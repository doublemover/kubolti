# GDAL Programs and CLI (Current)

Source: https://gdal.org/programs/

## Why it matters
This is the authoritative index for GDAL command line tooling, including the new unified `gdal` CLI.

## Key points
- GDAL 3.11 introduces a single `gdal` entry point with subcommands and a migration guide.
- The new CLI is labeled provisional and may change until it is formally frozen.
- Useful raster subcommands for this project include `gdal raster convert`, `gdal raster reproject`, `gdal raster tile`, and `gdal raster mosaic`.
- The CLI also supports pipelines (`gdal pipeline`, `gdal raster pipeline`) for chaining steps.

## Gotchas
- Treat the `gdal` CLI as evolving; legacy utilities remain available and may be more stable for scripting.
