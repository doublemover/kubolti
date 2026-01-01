# GDAL OSR Axis Order

Source: https://gdal.org/en/stable/tutorials/osr_api_tut.html

## Why it matters
Axis order behavior changed in GDAL 3, which can silently swap lon and lat if not handled explicitly.

## Key points
- Before GDAL 3.0, OGRSpatialReference ignored authority axis order; geographic coordinates were treated as lon,lat.
- Starting with GDAL 3.0, authority axis order is honored by default; EPSG:4326 and WGS84 are lat,lon.
- To force traditional GIS order, call SetAxisMappingStrategy(OAMS_TRADITIONAL_GIS_ORDER) on the SRS (or its clone).
- OAMS_AUTHORITY_COMPLIANT is the default mapping strategy; OAMS_CUSTOM allows manual mapping.

## Gotchas
- Mixing legacy assumptions with GDAL 3 can silently swap axis order; set a mapping strategy explicitly in all CRS transforms.
