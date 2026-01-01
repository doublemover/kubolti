# Ortho4XP EPSG:4326 Forum Thread

Source: https://forums.x-plane.org/forums/topic/291338-ortho4xp-tiles-epsg4326-wgs84/

## Why it matters
Spec v0.2 cites this thread to clarify EPSG:4326 and WGS84 expectations in Ortho4XP workflows.

## Key points
- EPSG:4326 is a geographic coordinate system for WGS84 (not a projection); EPSG:3857 is a projected WGS84 system.
- The datum match is what matters; coordinates referenced to WGS84 can be displayed in either system via reprojection.
- X-Plane uses EPSG:4326 for DSF, including raster data; Ortho4XP should convert imagery into 4326 before DSF output.
- Provider definitions may specify `grid_type=webmercator` or an `epsg_code`; Ortho4XP uses pyproj for conversions.

## Gotchas
- If inputs are not converted to EPSG:4326 before DSF output, tiles can be unusable.
