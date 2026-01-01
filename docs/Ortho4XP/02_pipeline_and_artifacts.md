# 02 — Pipeline & artifacts (what each step produces)

Ortho4XP is commonly executed as a “batch build” (one button), but it is conceptually a sequence:

## Step 1: Build vector data
Inputs:
- OSM extracts (airports, roads, coastline, inland water)
- airport patches (auto-patch + user patches)

Outputs:
- intermediate polygon + node data used for mesh building
- cached OSM files under `OSM_data/...`

What to validate in a wrapper:
- OSM download works (network, TLS)
- you have a strategy for “purge OSM data” when stale/corrupt caches cause issues

## Step 2: Build base mesh
Inputs:
- DEM tiles (default or custom)
- vector constraints from Step 1
- triangulation settings

Outputs:
- triangulated mesh (Triangle4XP)
- mesh artifact: `zOrtho4XP_.../Data+DD+DDD.mesh`

What to validate:
- DEM is present / loadable
- triangulation can fail (tiny triangles / precision issues). Your wrapper should capture the exact tile config and provide automatic retry modes.

## Step 2.5: Build masks (optional but common)
Inputs:
- land/sea/coastline/water boundaries
- mask settings (mask zoom, width, modes)

Outputs:
- mask textures used to blend coastlines / water transitions

Wrappers should:
- expose masks carefully (they affect disk size and water edges)
- provide sane defaults per XP11 vs XP12 expectations

## Step 3: Build tile (imagery + DSF)
Inputs:
- imagery provider(s)
- zoom level rules (global + custom ZL zones)
- mesh + masks

Outputs (the “tile scenery pack”):
- `zOrtho4XP_.../Earth nav data/<bucket>/<tile>.dsf`
- `zOrtho4XP_.../terrain/*.ter`
- `zOrtho4XP_.../textures/*.(dds|png)`

Practical note:
- community guides emphasize that this step can be slow and storage-heavy; wrappers should show a size estimate or at least warn strongly for high ZL.

## Overlay extraction
Inputs:
- an overlay source directory (commonly: `X-Plane …/Global Scenery/X-Plane … Global Scenery`)
- tile bounds

Outputs:
- overlay DSFs in `yOrtho4XP_Overlays/Earth nav data/.../*.dsf`

A wrapper should:
- validate `custom_overlay_src` points to a directory that actually contains `Earth nav data`
- fail fast with a helpful message when it doesn’t

## Outputs you should treat as “the deliverable”
For most end-users, the deliverable is:
- the `zOrtho4XP_...` folder(s) in X‑Plane’s `Custom Scenery`
- optionally `yOrtho4XP_Overlays` (also in `Custom Scenery`)

Intermediate caches (OSM/DEM/imagery) should be:
- kept if you care about speed & reproducibility
- purgeable if you care about disk space

## Observability: parse logs into structured events
Ortho4XP console output contains structured milestones (e.g., “Step 1/Step 2…”, “Downloading …hgt”, “Start of the mesh algorithm Triangle4XP”, “Converted text DSF to binary DSF”, etc.).
A production wrapper should:
- stream logs to UI
- tag milestones into machine-readable events
- attach the final tile cfg + log bundle to failures
