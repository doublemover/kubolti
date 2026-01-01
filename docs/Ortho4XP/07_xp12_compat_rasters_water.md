# 07 — XP12 compatibility (v1.40 transition): rasters, water, and overlay source nuance

## What changed with XP12-focused Ortho4XP work
The upstream repository README notes:
- the project is transitioning to version 1.40
- 1.40 is “mostly a compatibility update for XP12 water requirements”
- new tiles “automatically bring the seasons, sounds, etc raster from the corresponding Global Scenery tiles”
- the code has been updated for newer versions of dependencies (Numpy / Pyproj / Shapely), with an additional optional dependency (`skfmm`) needed only for `distance_masks_too`

Wrapper implications:
- You can no longer assume an XP11-only “base mesh + overlays” worldview.
- The XP12 toolchain may require:
  - additional raster extraction / copying from Global Scenery
  - new water/bathymetry behavior

## Overlay source nuance: XP11 vs XP12 Global Scenery
Community posts mention that some errors can be related to XP11 not having bathymetry data, and recommend setting `custom_overlay_src` to the XP12 Global Scenery directory even if using tiles in XP11.

Wrapper guidance:
- explicitly let the user choose overlay source *and* detect which X‑Plane version it corresponds to
- if a user is building tiles “for XP11 but using XP12 data”, allow it—but be explicit

## Water & coastline rendering
XP12 introduced stricter water/coast expectations; the Ortho4XP project mentions updated water requirements and some newer work related to 3D waterbed rendering.

Wrapper guidance:
- provide XP11 and XP12 presets for:
  - water masks
  - coastline curvatures / simplifications
  - sea smoothing
- expose a clear “water mode” choice instead of a pile of low-level toggles

## Practical versioning guidance
Ortho4XP is used through:
- Python + dependencies, or
- prebuilt binaries (varies over time)

Wrappers should:
- detect and report:
  - Ortho4XP version/branch
  - Triangle4XP binary version
  - key Python dependency versions
- store this version info in the tile’s provenance record
