# 05 — Custom DEMs & mesh refinement

## Why custom DEM support matters
Ortho4XP’s default DEM source aims for wide coverage (commonly void-filled SRTM-derived data). For many regions, the best elevation data is country/state-specific and may require preprocessing.

Ortho4XP users often want:
- better mountain detail (Alps, Himalayas, etc.)
- accurate airport surroundings
- fewer “holes” / spikes caused by no-data areas

## Requirements for custom DEM files
A commonly cited set of requirements (older Ortho4XP versions, but still a good baseline):

- full tile coverage (1° x 1°)
- `.hgt` or `.tif` (GeoTIFF) format
- WGS84 projection
- no-data value of `-32768`

If your wrapper accepts “drop in a DEM”, validate these early.

## Where Ortho4XP expects DEM files
If you’re using `.hgt` tiles:
- filenames use N/S and E/W (e.g., `N47E030.hgt`)
- they live under 10°x10° bucket folders, e.g. `Elevation_data/+40+030/`

A wrapper should:
- compute the correct bucket folder from the tile coordinates
- show users exactly where a file is expected to land

## Multi-DEM refinement (iterate workflow)
Oscar describes a refinement workflow:
- run Step 2 multiple times—once per DEM
- increase `iterate` each time (`0`, `1`, `2`, …)
- `iterate=0` uses the base DTM and produces an initial mesh
- `iterate=1` refines the mesh using information from a second DEM
- you can go back by dialing down `iterate` if too many triangles were added

Important nuance:
- For iterates >= 1, you often want to disable “fill no_data” for DEMs that have no-data regions, to avoid artifacts from aggressive filling.

Wrapper design pattern:
- expose DEMs as an ordered “stack”
- show an explicit run plan:
  - Step 1 once
  - Step 2 repeated N times with `iterate=i`
  - Step 2.5 optional
  - Step 3 once
- cache per-iterate artifacts to support resuming and comparing outputs

## Practical preprocessing suggestions (wrapper features)
If you want to “do it right”:
- provide a small “DEM validator” utility
  - verify projection / coverage
  - inspect no-data percentage
  - confirm numeric ranges and units
- optionally provide scripts or guidance for cropping/merging DEMs into 1° x 1° tiles
- log exactly which DEM file(s) were used for a tile and store that with the tile cfg

## Debugging “flat mesh” outcomes
When meshes are flat or obviously wrong:
- confirm Ortho4XP is loading the intended DEM (log shows which `.hgt/.tif` is used)
- ensure the expected DEM file exists in the correct `Elevation_data/...` bucket folder
- confirm you’re not accidentally generating with defaults due to failing to load the intended tile cfg
