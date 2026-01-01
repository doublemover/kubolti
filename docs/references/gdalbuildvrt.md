# GDAL gdalbuildvrt Utility

Source: https://gdal.org/programs/gdalbuildvrt.html

## Why it matters
`gdalbuildvrt` builds virtual mosaics, which is a low-cost way to merge many DEM tiles without duplicating data.

## Key points
- Builds a VRT from an input list or `-input_file_list` text file.
- Controls output resolution with `-resolution` and `-tr`.
- Supports `-separate` to put each input into its own band.
- `-addalpha`, `-srcnodata`, and `-vrtnodata` control nodata and transparency behavior.
- For very large mosaics, GDAL 3.9+ recommends using `gdaltindex` with the GTI driver.

## Gotchas
- By default, overlapping inputs are prioritized by list order; alpha is not composited.
- Inputs with mismatched characteristics are skipped unless `-strict` is set.
