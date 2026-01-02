# File Formats and Artifacts

Source: DEM2DSF spec + implementation (internal reference).

## Why it matters
DEM2DSF moves data through multiple formats. Understanding what each file encodes helps debug failed builds and keep outputs compatible with Ortho4XP and X-Plane.

## Key points
- GeoTIFF tile DEMs: EPSG:4326, 1x1 degree bounds, nodata defined (Ortho4XP defaults
  to -32768). Optional LZW/DEFLATE compression via `--normalized-compression`.
- VRT mosaics: virtual datasets that merge multiple DEM inputs with consistent CRS and resolution before tiling
  (use `--mosaic-strategy vrt`; default `full` builds a GeoTIFF mosaic, `per-tile` streams merges per tile).
- DSF tiles: produced per `+DD+DDD` tile under `Earth nav data/<bucket>/<tile>.dsf`
  (bucket is the 10x10 folder like `+40+000`). Optional 7z compression is allowed,
  but DSFTool 2.2+ is required to read 7z-compressed DSFs directly.
- Terrain files (`.ter`): text references to texture assets. Overlay drape updates texture lines (TEXTURE, BASE_TEX, TEXTURE_LIT).
- Textures (`.dds` or `.png`): overlay drape copies these into `textures/` and rewires terrain references.
- Build artifacts:
  - `build_plan.json`: inputs, backend, options, and provenance.
  - `build_report.json`: per-tile status, warnings/errors, artifacts.
  - `manifest.json`: file list + hashes for published builds.
  - `audit_report.json`: counts, sizes, DSF compression summary.
- Tool discovery:
- `tools/tool_paths.json` maps tool names to executable/script paths (dsftool, ddstool, ortho4xp, 7zip).
- DEM stack config (`dem_stack.json`):
  - `layers`: array of `{path, priority, aoi?, nodata?}`.
- Patch plan (`patch_plan.json`):
  - `schema_version` + `patches` list with `tile`, `dem`, optional `aoi`, optional `nodata`.
- Overlay report (`overlay_report.json`):
  - generator name, artifacts, warnings/errors, tiles.
- Runner events (`*.events.json`):
  - schema version, runner name, optional tile/attempt, and structured events
    with stream/line context.
- DSF2Text rules (DSFTool):
  - `DIVISIONS`, `HEIGHTS`, and `PROPERTY` should precede other commands.
  - Tile bounds properties (`sim/west`, `sim/south`, `sim/east`, `sim/north`) must
    be the final PROPERTY lines in the file.
  - Raster layers require RAW sidecar files that match the `RASTER_DATA` width/height,
    bpp, scale, and offset.

## Gotchas
- For Ortho4XP, keep nodata consistent and avoid unexpected voids; use fill strategies when needed.
- DSF file names must match the tile name and live under the correct bucket
  (`Earth nav data/+40+000/+47+008.dsf`).
- Terrain texture updates are line-based; only recognized texture keys are rewritten.
- DSFTool is sensitive to line endings; prefer UTF-8 text with LF newlines.
