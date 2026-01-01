# 03 — Folder layout & conventions (critical for automation)

## Tile folder naming
Ortho4XP tiles are typically stored as scenery pack folders like:

- `zOrtho4XP_+47+008/`
- `zOrtho4XP_+32-116/`

Some tooling (and some Ortho4XP logic) assumes this naming; community tooling warns that merging tiles into a single folder can “destroy compatibility with Ortho4XP itself” because it expects a `zOrtho4XP_` tile folder per tile.

## Inside a `zOrtho4XP_...` tile pack
Community posts show a typical structure:

- `Data+DD+DDD.mesh`
- `Earth nav data/+LL+LLL/+DD+DDD.dsf`
- `terrain/*.ter`
- `textures/*.(dds|png)`

This matters for your wrapper because:
- the DSF is not at the root; it’s under a *bucket folder*
- post-processing steps usually need to locate DSFs by coordinate

## DSF “bucket folders” (Earth nav data)
X‑Plane scenery stores DSFs like:

`Earth nav data/+30-120/+32-116.dsf`

Where the intermediate folder is by 10°x10° buckets (multiples of 10).

## Elevation data (HGT) bucketing
Ortho4XP elevation files are also bucketed in 10°x10° folders. Example guidance:

- Tile `+47+030` uses `N47E030.hgt`
- That file goes in `Elevation_data/+40+030/` (because +40 and +30 are the 10-degree buckets)
- Each bucket folder covers 100 tiles (10 x 10)

If your wrapper supports “drop your own .hgt files here”, it should:
- compute the correct bucket folder automatically
- validate filenames (N/S, E/W) and the “south-west corner” convention

## Tile-specific cfg file (provenance)
X‑Plane.org support threads note:
- “In the root directory of both tiles, there should be a cfg file that lists the selected parameter settings”
That cfg is an essential reproducibility artifact: store it, archive it, and treat it as the tile’s “build manifest”.

Also, there are references to tile-specific config files with a naming pattern like:
- `Ortho4XP_+XX+YYY.cfg` (in the target scenery folder)
depending on Ortho4XP version/branch.

## Base folder gotchas
At least one community thread points out that how you specify the base folder can affect whether Ortho4XP interprets it as:
- the *full output path*, or
- a prefix where it will create `zOrtho4XP_+DD+DDD`

If your wrapper constructs paths, be strict and consistent:
- normalize separators
- avoid “optional trailing slash” ambiguity
- write tests for path handling on Windows/macOS/Linux
