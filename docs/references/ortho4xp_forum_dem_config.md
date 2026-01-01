# Ortho4XP DEM Config Forum Thread

Source: https://forums.x-plane.org/forums/topic/156476-question-regarding-elevation-data-and-ortho4xp-config-file/

## Why it matters
Spec v0.2 cites this thread for community DEM requirements and configuration details.

## Key points
- Default online DEM: viewfinderpanoramas.org (void-filled SRTM 3-arcsecond, ~90m); no single higher-res global source is called out.
- Country or region DEMs are often better but require preprocessing; Ortho4XP 1.3 supports local mesh refinement with multiple geo-referenced DEMs per tile.
- Ortho4XP 1.20b has no config option for a custom online DEM provider; use "Use custom DEM file" instead.
- Custom DEM requirements (1.20b): full 1x1 degree tile coverage, .hgt or .tif, WGS84 projection, NoData value -32768.

## Gotchas
- Manual DEM prep is required for high-res sources; plan for reprojection and tiling before feeding Ortho4XP.
