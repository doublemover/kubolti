# GIS StackExchange: Split Raster into Tiles

Source: https://gis.stackexchange.com/questions/14712/splitting-raster-into-smaller-chunks-using-gdal

## Why it matters
DEM preprocessing often requires cutting large rasters into consistent tiles before feeding Ortho4XP or DSF tooling.

## Key points
- Use `gdal_retile.py` for batch tiling with `-ps` tile size, output format, overlap, and optional tile index output.
- Example: `gdal_retile.py -ps 512 512 -targetDir C:\tiles input_dem.tif`.
- `gdal_translate` supports tiling via `-srcwin` (pixel windows) or `-projwin` (georeferenced windows) inside a loop.
- Edge tiles can be smaller by clamping width and height to raster bounds.
- `gdalwarp -te ... -multi -wo NUM_THREADS=ALL_CPUS` can tile by extents, but runs are often IO bound.

## Gotchas
- `-projwin` expects map coordinates, not pixel values; mixing them yields empty windows.
- Parallelizing tiling helps only if disk IO keeps up.
