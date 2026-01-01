# GDAL gdal_translate Utility

Source: https://gdal.org/programs/gdal_translate.html

## Why it matters
`gdal_translate` is the primary tool for format conversion, subsetting, and lightweight resampling of rasters.

## Key points
- Converts between raster formats with `-of` and data types with `-ot`.
- Spatial subsetting uses `-srcwin` (pixel window) or `-projwin` (georeferenced window).
- Resolution and size can be set with `-tr` or `-outsize`.
- Resampling method is selected with `-r` (nearest, bilinear, cubic, etc.).
- The new CLI equivalent is `gdal raster convert`, with `gdal raster clip` for subsetting.

## Gotchas
- `-projwin` expects map coordinates; `-srcwin` expects pixel offsets and sizes.
- `-tr` is mutually exclusive with `-outsize`.
