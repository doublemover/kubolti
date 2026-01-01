# 04 — Configuration surface area (high-leverage knobs)

Ortho4XP has *many* settings. A wrapper should not expose everything at once—start with the few that strongly affect quality, performance, and success rate.

Below are knobs that show up repeatedly in real-world debugging logs and “known-good” configs.

---

## A. Mesh density & triangle behavior (Step 2)

### `mesh_zl`
- Conceptually the “mesh resolution” (separate from imagery ZL).
- Oscar Pilote notes that `mesh_zl` should be **at least as large as the maximum imagery ZL used**, otherwise “tearing will appear for some triangles” (i.e., mismatched sampling can create artifacts).

Wrapper guidance:
- If you expose custom imagery ZL zones, compute an implied minimum `mesh_zl` and warn if the user goes below it.

### `curvature_tol`
- The most common “triangle explosion” control.
- Lower values generally mean more triangles and a more detailed mesh.
- Community experimentation shows huge triangle count swings (e.g., ~13M vs ~3.6M triangles for the same tile when changing curvature tolerance).

Wrapper guidance:
- Provide a “triangle budget” view: estimate mesh complexity and warn before generating extremely dense meshes.

### `limit_tris`
- A safety cap to avoid excessive triangle counts.
- Consider exposing this as “Max triangles (millions)” with sensible presets.

### `min_angle`
- Mesh quality / stability parameter for triangulation.
- When Triangle4XP fails with tiny triangles / precision issues, community advice often involves reducing the minimum allowable angle (and/or increasing area thresholds) to prevent creation of tiny triangles.

Wrapper guidance:
- Treat `min_angle` as a fallback knob: auto-retry with smaller values (e.g., 10 → 5 → 0) on known Triangle4XP failure messages.

### `min_area`, `max_area`, `clean_bad_geometries`
- These influence geometry cleanup and triangulation constraints.
- Oscar’s “south Norway mesh” settings list includes:
  - `min_area`, `max_area`, and `clean_bad_geometries=True`

Wrapper guidance:
- Expose as “Advanced mesh stability” rather than surfacing raw numbers to novices.
- Include an auto “safe mode” preset.

---

## B. Airports, roads, and “flattening” behavior (Step 1 / Step 2)

### `apt_smoothing_pix`
- Appears in many real tile configs and logs.
- Impacts how elevation is smoothed over airports (helps with bumpy runways).

### `road_level`, `road_banking_limit`, `lane_width`, `max_levelled_segs`
- Influence road inclusion and road leveling/banking.
- These show up in Oscar’s settings list, and also in error stack traces (e.g. missing `lane_width` when versions mismatch).

Wrapper guidance:
- Make “roads & overlays quality” a separate control from “mesh density”.
- Detect version skew (cfg referencing a parameter not supported by the installed Ortho4XP build) and warn early.

---

## C. Water & masks (Step 2.5 / Step 3)

Typical parameters seen in tile build logs:
- `mask_zl`, `masks_width`, `masking_mode`
- `sea_smoothing_mode`, `water_smoothing`
- `use_masks_for_inland`, `imprint_masks_to_dds`

Wrapper guidance:
- Provide XP11 vs XP12 presets; water rendering expectations differ.
- If users complain about coastlines/water edges: surface the mask knobs and provide a preview workflow.

---

## D. Multi-DEM refinement (Step 2 repeated)

### `iterate`
Oscar describes running Step 2 multiple times, incrementing `iterate` each time:
- `iterate=0` produces a first mesh from the base DTM/DEM
- `iterate=1` refines using a second DEM
- You can repeat for multiple DEMs and “dial down iterate” to revert.

Related knobs:
- `fill no_data` is often recommended **False** for higher iterates (>=1) depending on DEM characteristics.

Wrapper guidance:
- If you support “multi-DEM”, model it as a list:
  1) base DEM
  2) refinement DEMs with an order
- Provide an “N iterates planned” plan view and clear caching rules.

---

## E. Imagery providers (Step 3)

Ortho4XP supports many providers; keep selection user-driven.
For WMS sources, Oscar mentions:
- WMS version mismatches (1.1.1 vs 1.3.0)
- Performance/efficiency differences between WMS and tile servers
- That textures end up in EPSG:3857, so prefer a WMS offering that projection to reduce warping.

Wrapper guidance:
- Make provider selection explicit and user-driven.
- Store provider metadata in the tile’s provenance record.
- Avoid shipping imagery; keep downloads client-side.
