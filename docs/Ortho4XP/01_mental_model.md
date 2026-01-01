# 01 — Mental model (what Ortho4XP is doing under the hood)

## The “product” Ortho4XP generates

A finished Ortho4XP tile is *not* “a big JPEG”. It is a complete X‑Plane scenery pack:

- **Base mesh + ortho textures**: `zOrtho4XP_+DD+DDD/`
  - A DSF (the mesh + texture mapping) under `Earth nav data/.../*.dsf`
  - Terrain `.ter` files and textures (`.dds`, sometimes `.png`)
  - A `Data+DD+DDD.mesh` (mesh artifact used by Ortho4XP)
- **Overlay scenery**: `yOrtho4XP_Overlays/`
  - DSF overlays extracted from *some existing scenery source* (usually X‑Plane Global Scenery)

The base mesh determines the ground elevation/shape and also controls what can “sit” on top. The overlay DSFs provide things like roads, autogen placement, forests, etc. If users complain about “no roads/buildings”, that is usually an overlay extraction or scenery ordering problem rather than an orthophoto problem.

## Why wrappers tend to break

### 1) Statefulness & hidden caches
Ortho4XP caches:
- OSM extracts (`OSM_data/...`)
- elevation data (`Elevation_data/...`)
- provider tiles / imagery caches (depends on setup)
- tile-specific cfg (saved into the tile’s output folder)

A wrapper that treats Ortho4XP as stateless will produce inconsistent results, especially when rerunning a failed tile.

### 2) Two very different outputs (mesh vs overlay)
A “tile build” often needs:
- **mesh build** for `zOrtho4XP_...`
- **overlay extraction** to populate `yOrtho4XP_Overlays`

Your UX should make it explicit:
- “Generate mesh+ortho textures”
- “Extract overlays from Global Scenery/HD mesh”
…and should validate the user’s overlay source path before starting.

### 3) A geometry pipeline that sometimes needs retries
Ortho4XP uses a triangulation step (“Triangle4XP”) which can fail on edge cases. The fix is frequently *parameter adjustment* (e.g., `min_angle`, area limits) and retry—meaning your wrapper should make retries a first-class feature.

### 4) XP12 differences (v1.40 transition)
The current repo’s README explicitly notes the transition to v1.40 for X‑Plane 12 water requirements, and that newer tiles also bring additional rasters such as seasons/sounds from Global Scenery. A wrapper that “assumes XP11 forever” will confuse users.

## Design principles for Ortho4XP-based tooling

1. **Make state explicit**: choose cache directories; show what’s reused vs recomputed.
2. **Capture provenance**: store tile cfg + imagery provider + DEM source metadata with every tile.
3. **Separate concerns**:
   - mesh generation settings (triangulation density, smoothing, DEM)
   - imagery settings (provider, zoom levels, mask behavior)
   - overlay settings (overlay source path, overlay extraction toggles)
4. **Treat the triangulator as unreliable**:
   - detect known failure patterns
   - apply controlled fallback strategies (see doc 08)
5. **Be conservative on licensing**:
   - never ship imagery; only automate end-user downloads
   - make sources user-selectable
