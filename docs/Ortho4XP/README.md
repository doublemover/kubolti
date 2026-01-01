# Ortho4XP — research notes for designing/building/enhancing an Ortho4XP-based tool (wrapper/generator)

These notes are aimed at **people building tooling around Ortho4XP** (automation, backends, pipelines, “one-click” generators, CI tile builds, etc.), not at end-user “how to click the GUI” tutorials.

Ortho4XP is widely used to generate:
- **base mesh tiles** + orthophoto textures (`zOrtho4XP_...`)
- **overlay scenery** extracted from X‑Plane Global Scenery (`yOrtho4XP_Overlays`)

Ortho4XP’s author has been transitioning toward **v1.40 for X‑Plane 12 compatibility**, including XP12 water requirements and additional rasters (seasons/sounds/etc.) coming from Global Scenery (see SOURCES.md).

## What’s inside

1. `01_mental_model.md` — core concepts, what Ortho4XP *actually* produces, and why wrappers fail
2. `02_pipeline_and_artifacts.md` — steps (vector → mesh → masks → imagery/DSF → overlays) and resulting files
3. `03_folder_layout_and_conventions.md` — where outputs live, DSF “bucket” folders, tile naming rules
4. `04_configuration_surface_area.md` — high-leverage config knobs and how to expose them safely
5. `05_custom_dem_and_refinement.md` — custom DEM requirements, multi-DEM refinement (`iterate`), and gotchas
6. `06_overlays_and_scenery_order.md` — overlay extraction, `custom_overlay_src`, and `scenery_packs.ini` ordering rules
7. `07_xp12_compat_rasters_water.md` — what changes in XP12/v1.40 and what a wrapper must handle
8. `08_failure_modes_and_resilience.md` — common failures and robust fallback strategies
9. `09_automation_integration_checklist.md` — concrete checklist for productionizing Ortho4XP runs
10. `SOURCES.md` — primary links used

## Quick framing for a “DSF toolchain” wrapper

If your tool is ultimately generating **DSF base meshes** (and optionally overlays) programmatically, the big recurring themes are:

- **State & caching:** Ortho4XP is not “pure”. It caches OSM, DEM, imagery, tile cfg, etc. Make caching explicit.
- **Reproducibility:** capture the tile-specific `.cfg` and the provider settings that created the tile.
- **Resilience:** errors often require *parameter nudges* (e.g., Triangle4XP `min_angle`, area limits) and reruns.
