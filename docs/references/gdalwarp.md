# gdalwarp

Source: https://gdal.org/en/stable/programs/gdalwarp.html

## Why it matters
gdalwarp is the core reprojection and warping tool for DEM normalization.

## Key points
- gdalwarp reprojects and warps rasters; it can mosaic multiple inputs.
- Common options: -s_srs, -t_srs, -tr, -te and -te_srs, -r, -srcnodata and -dstnodata, -cutline and -crop_to_cutline, -tap, -overwrite.
- Resampling methods include near, bilinear, cubic, cubic spline, lanczos, average, and others; downsampling uses overviews by default.
- Multiple inputs are processed in order; to avoid edge effects, build a VRT first with gdalbuildvrt.
- Vertical transformations can apply when source or target CRS includes vertical datum; PROJ grid files may be required.

## Gotchas
- Overviews may use a different resampling kernel than -r; use -ovr NONE when you need exact control.
- Nodata handling affects interpolation; align nodata values across inputs or set -srcnodata per file.
