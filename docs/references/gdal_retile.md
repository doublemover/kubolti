# GDAL gdal_retile Utility

Source: https://gdal.org/programs/gdal_retile.html

## Why it matters
`gdal_retile` is the official GDAL utility for cutting rasters into tiles and generating pyramids.

## Key points
- Retiles inputs into a target directory and can build pyramid levels.
- Inputs must share a coordinate system, band count, and have no rotation in the geotransform.
- Tile size uses `-ps` (default 256x256) with optional `-overlap`.
- Output can include a tile index shapefile (`-tileIndex`) or CSV (`-csv`).
- The utility is Python-based and requires GDAL Python bindings.

## Gotchas
- Pyramids are generated from the original inputs, not intermediate levels.
- Use `-useDirForEachRow` when output directories would otherwise contain too many files.
