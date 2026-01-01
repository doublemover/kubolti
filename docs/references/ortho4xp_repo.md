# Ortho4XP Repository

Source: https://github.com/oscarpilote/Ortho4XP

## Why it matters
Ortho4XP is the baseline backend; dem2dsf wraps it and must stay compatible with its inputs and outputs.

## Key points
- Ortho4XP is a scenery generator for the X-Plane flight simulator.
- The README notes a transition to version 1.40 with XP12 compatibility updates, especially for water behavior.
- New tiles can copy seasons and sounds rasters from Global Scenery (XP12).
- Dependencies are updated for recent numpy, pyproj, and shapely; skfmm is optional for distance_masks_too.

## Gotchas
- XP12 water and raster behavior can differ from XP11 defaults; keep configuration version-aware.
