# DSF Usage in X-Plane

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/

## Why it matters
This is the low-level definition of what X-Plane accepts in DSF files, including required properties and raster layers.

## Key points
- DSF is a container format; X-Plane recognizes specific property names and data layouts.
- Required bounding properties: sim/north, sim/south, sim/east, sim/west. Bounds are integer degrees. sim/planet is optional and defaults to earth.
- X-Plane 10+ can load DSF files compressed as a single 7z archive; compression is optional.
- Raster layers include elevation DEM, bathymetric depth, sound rasters (XP12), and seasonal rasters (XP12).
- Elevation may be sourced from raster data; the doc notes a vertex elevation flag value of -32768.0 for raster usage.
- With raster elevation, normal vectors can be left at 0.0 and X-Plane derives them.

## Gotchas
- XP12 seasonal support expects eight rasters (start and end for four seasons); missing layers break the set.
- Tools may need DSF uncompressed; plan for 7z handling in validation and packaging.
