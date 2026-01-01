# DEM2DSF XP12 Mesh Pipeline
**Internal Specification (Updated v0.2)**  
**Date:** 2025-12-27  
**Target:** X-Plane 12 (XP12)

---

## 0. What changed in v0.2

This revision removes the over-constraints that assumed the *input* DEM already matches X‑Plane tile expectations.

### Key updates
- **Input DEM can be any extent** (not guaranteed to be exactly 1×1 degree). We will **tile/crop/merge** into the required DSF tile grid.
- **Input DEM can be any supported CRS**, including **ETRS89** (geographic or projected, e.g., ETRS89/UTM). We will **reproject** to a backend-compatible CRS during preprocessing.
- The earlier statement “DEM must be geographic, exact tile, pixel-is-point, no voids” is now framed as:
  - **backend-specific requirements** that apply to our **normalized per-tile DEM artifact**, not to the raw input.
- Added explicit design for:
  - **mosaicing** multiple DEM sources,
  - **resampling policies** (up/downsampling),
  - **partial-coverage completion strategies** (how to fill missing areas),
  - **GDAL 3 axis-order safety**.

---

## 1. Executive summary

We are building a repeatable pipeline and “wizard” that ingests **GeoTIFF raster terrain models** (DEMs) and produces **XP12 base-mesh DSF tiles** with configurable density and XP12-friendly raster layers where feasible.

Because DSF base meshes are **1×1 degree tiles**, all workflows ultimately normalize data into that tiling scheme, even when the source DEM is a mosaic or a small-area dataset.

In the XP community, the common practice is to use GIS tools (QGIS/GDAL) to:
1) mosaic local DEMs,  
2) reproject to WGS84,  
3) clip to the 1×1 tile extent,  
4) export a GeoTIFF for the mesh generator.  
(Example community guidance for Ortho4XP users explicitly describes exactly this preprocessing flow.)  
`dem2dsf` internalizes this workflow so users don’t need to be GIS experts.

---

## 2. Background and ecosystem context

### 2.1 X‑Plane 12 base meshes
- A **base mesh** is terrain formed from **triangles**, packaged inside a **DSF file** for a **1×1 degree tile**.
- DSFs can also carry **raster layers**. XP12 uses additional rasters such as **soundscape** and season boundaries; XP12 quality outcomes depend on these being present/consistent for many regions and conditions.

### 2.2 Existing mesh workflows (reference behavior we should match)
This project is not operating in a vacuum; popular tools constrain how data is prepared:

- **Ortho4XP (XP community standard)**  
  A common workflow requires a **full 1×1 tile** custom DEM in **WGS84** with a **NoData value** (often `-32768`) before the tool is happy. Community guidance for older versions explicitly states these requirements (full tile coverage, WGS84 projection, nodata value).  
  Ortho4XP also supports local refinement with multiple DEMs per tile (multi-resolution) in newer versions, which we treat as an advanced capability for later phases.

**Conclusion:** we must design a robust **DEM normalization layer** that:
- accepts arbitrary CRS/extents/resolutions,
- outputs Ortho4XP-ready per-tile DEM artifacts that satisfy its expectations.

---

## 3. Goals and non-goals

### 3.1 Goals (v1–v2)
1. Accept **GeoTIFF DEM(s)** in arbitrary CRS (including **ETRS89**) and arbitrary extent.
2. Produce **XP12 base mesh DSF** tiles for intersecting 1×1 degree tiles.
3. Provide **configurable mesh density** through backend-agnostic presets with backend-specific mapping.
4. Provide a **wizard** that:
   - validates inputs,
   - performs or proposes required preprocessing (reproject/resample/tile),
   - requests additional data when needed (e.g., missing coverage),
   - produces actionable quality warnings and sensible defaults.
5. Support an **AutoOrtho-friendly** output mode (Ortho4XP naming conventions, no-large-imagery packaging) where feasible.
6. Provide **deterministic build outputs** (config snapshot + provenance).

### 3.2 Non-goals (v1)
- Building a new triangulation engine from scratch (we start by orchestrating Ortho4XP).
- Downloading imagery/orthophotos.
- Automatically fixing all vertical datum issues (we will record, validate, and optionally apply known transforms if configured).

---

## 4. Inputs and outputs

### 4.1 Primary inputs
- `--dem` one or more DEM files (GeoTIFF; optionally .hgt if supported)
- Optional:
  - `--aoi` polygon (GeoJSON/shapefile) for “build only where needed”
  - `--tile` one or more X‑Plane tiles (`+DD+DDD` naming)
  - `--quality` {`compat`, `xp12-enhanced`} (see §9)
  - `--autoortho` boolean

### 4.2 Supporting inputs (wizard-queried)
- Additional DEM(s) to fill gaps (when the primary DEM does not fully cover required tiles)
- Optional water masks / coastlines / bathymetry DEM
- Optional “global scenery” DSF folder for XP12 raster copying/enrichment
- Optional airport boundary/flattening constraints (future)

### 4.3 Outputs
Per tile:
- `Earth nav data/<bucket>/<tile>.dsf` where bucket is the 10x10 folder
  (e.g., `Earth nav data/+40+000/+47+008.dsf`).
- Supporting terrain resources (`.ter`, textures if applicable)
- `build_report.json` + `build_plan.json` (provenance, settings, warnings)
Optional:
- zipped scenery pack artifact
- 7z-compressed DSF packaging (XP supports DSF in 7z archives)

---

## 5. Core design: canonical “Tile DEM” normalization

### 5.1 Canonical Tile DEM artifact (internal)
For each X‑Plane tile, the pipeline produces a **normalized DEM** artifact that is backend-ready.

**Canonical fields recorded in metadata**
- Source files (paths + checksums)
- Source CRS (WKT/EPSG)
- Target CRS used for backend (default: `EPSG:4326`)
- Resampling method
- Target resolution
- Nodata strategy (value + fill behavior)
- Vertical units assumption (meters; and any applied scaling)
- Coverage metrics: % of tile covered by source before fill, after fill

### 5.2 CRS policy: support any CRS (including ETRS89)
**Input CRS may be:**
- Geographic (lat/lon) in ETRS89 (e.g., EPSG:4258)
- Projected ETRS89 / UTM (e.g., EPSG:25832, 25833, etc.)
- Any other CRS PROJ/GDAL can interpret

**Normalization rule**
- Reproject to a backend canonical CRS (default `EPSG:4326`, WGS84 geographic).  
  This matches the “what Ortho4XP expects” and aligns with the DSF world grid (lat/lon tile bounds).

**GDAL axis order safety**
Starting with GDAL 3.0, authority axis order may be honored by default (lat/long) for EPSG:4326, which can break code that assumes long/lat. We must enforce a consistent axis order strategy in our transform/warp code paths.

### 5.3 Extent policy: input does NOT need to match 1×1 tiles
**Input DEM can be:**
- small AOI (e.g., only an airport region),
- large mosaic covering multiple tiles,
- irregular partial coverage across tiles.

**Normalization rule**
- Compute intersecting tiles from DEM bounds (or AOI polygon).
- For each tile, derive a tile-specific DEM by **warp + clip + resample + merge + fill**.

### 5.4 Partial-coverage completion strategy
Many DEM datasets won’t cover an entire 1×1 tile. Backends (especially Ortho4XP custom DEM workflows) commonly expect full tile coverage.

`dem2dsf` must offer explicit strategies when tile coverage is incomplete:

1) **Ask for additional DEM(s) to fill missing regions** (preferred offline mode)  
   - User can provide lower-res national DEM, SRTM, etc.
2) **Fetch fallback DEM from a configured provider** (optional mode; depends on networking)  
3) **Fill missing areas with constants** (last resort; causes cliffs/seams)
4) **Hybrid: “AOI-only mesh + patch”** (future; requires a patch backend)

Wizard should default to **(1)** or **(2)** and clearly warn when using (3).

### 5.5 Resampling policy (DEM-specific)
Resampling a DEM is unavoidable when reprojecting or matching a target grid.

Wizard exposes:
- **Target resolution** options:
  - “Preserve source resolution” (subject to caps)
  - “Clamp to max resolution” (e.g., 5m/10m/30m)
  - “Per-tile adaptive” (future)
- **Resampling kernels**
  - Upsampling: bilinear/cubic
  - Downsampling: average (recommended), or bilinear if smoother outcome is acceptable

We explicitly track resampling decisions in `build_plan.json`.

### 5.6 Nodata/void fill policy
Backends vary:
- Ortho4XP custom DEM guidance often relies on a known NoData value (e.g., `-32768`) and full tile coverage.

Our policy:
- Nodata is allowed in raw input.
- During canonicalization, we either:
  - fill voids (interpolate), and/or
  - fill with fallback DEM, and/or
  - fill with constant (warn heavily).

---

## 6. Backends

### 6.1 Ortho4XP backend (default for XP12)
**Why:** Ortho4XP is the most practical path to XP12 tile generation, and its recent updates are oriented around XP12 water/rasters.

**Backend expectations (normalized artifacts must satisfy)**
- Tile DEM in WGS84 (`EPSG:4326`) or equivalent geographic coordinate system.
- Full tile coverage, with a consistent NoData policy, to avoid triangulation failures and “holes.”

**Notable capability to plan for**
- Ortho4XP supports local refinement using multiple georeferenced DEM files at different resolutions per tile (multi-resolution DEM stack). We treat this as a planned “advanced feature” because it directly fits your “one DEM doesn’t cover everything / use best available” scenario.

## 7. Wizard UX (interactive workflow)

### 7.1 Wizard objectives
- “Do what QGIS/GDAL users do manually” (mosaic → reproject → clip → export), but in a guided, repeatable way.
- Reduce common failure cases (wrong CRS, wrong extent, nodata holes, unrealistic resolution causing mesh explosion).

### 7.2 Wizard flow (updated)
1) **Select build area**
   - choose: tiles, AOI polygon, or “auto from DEM bounds”
2) **Inspect DEM(s)**
   - detect CRS (or ask user if missing)
   - detect vertical units, nodata, outliers
3) **Choose normalization options**
   - target CRS (default: EPSG:4326)
   - target resolution + resampling method
   - nodata fill strategy
   - partial-coverage strategy (add fallback DEMs / fetch / constant fill)
4) **Choose density preset**
   - Ortho4XP preset mapping for `curvature_tol`/`mesh_zl`
5) **XP12 quality options**
   - XP12 raster enrichment (seasons, soundscape, etc.) via global scenery copy/merge when possible
6) **AutoOrtho mode**
   - enforce texture naming expectations and “no-download” style output if requested
7) **Build & validate**
   - run backend; run DSF validation; produce report and install guidance

---

## 8. Unified density model

We expose one conceptual model:

```json
{
  "density": {
    "preset": "medium",
    "limits": {
      "warn_triangles_per_tile": 1500000,
      "max_triangles_per_tile": 5000000
    },
    "targets": {
      "max_vertical_error_m": 5.0,
      "max_points_added": 120000
    }
  }
}
```

Density presets map to Ortho4XP configuration knobs (harvested and version-pinned).

---

## 9. XP12 quality and raster-layer compliance

### 9.1 Quality modes
- **compat**: produce a base mesh that loads, but may not include XP12-specific rasters.
- **xp12-enhanced**: validate and attempt to include/copy XP12 raster layers (e.g., soundscape, seasons) where possible.

### 9.2 Raster enrichment pass (post-processing)
A dedicated post-pass over DSFs that can:
- inspect DSF rasters,
- optionally copy/merge rasters from Global Scenery tiles,
- revalidate DSF.

This is aligned with what the XP community has built as separate “converter” utilities; we build it in as a first-class step.

---

## 10. AutoOrtho integration

AutoOrtho is a texture streaming layer that expects Ortho4XP-style texture naming and terrain references.

`dem2dsf` supports:
- **AutoOrtho-ready mesh-only packs** (no large imagery payload)
- Validation of texture naming conventions and references for compatibility.

---

## 11. Validation and packaging

### 11.1 Validation
- DSF decompile/recompile smoke test (DSFTool)
- Validate tile bounds properties
- Validate presence/absence of XP12 rasters when in `xp12-enhanced`
- Triangle count budget checks
- Border/seam sanity checks (best-effort; improved in later phases)

### 11.2 Packaging
- Output correct scenery folder layout
- Optional zipped artifact (“publish” step)
- Optional 7z-compressed DSF packaging

---

## 12. Tool command semantics

- Tool invocation flags (`--runner`, `--dsftool`) are **command lists**, not single-path strings.
- Preserve the full token list end-to-end, including wrapper prefixes (Wine, env, conda, etc.).
- Document quoting expectations for Windows vs POSIX shells.

---

## 13. Python dependencies (implementation guidance)

### 13.1 Must-have
- `rasterio` + GDAL backend
- `pyproj` (CRS transforms, datum conversions)
- `numpy`

### 13.2 Recommended
- `shapely` / `pyogrio` (AOI polygons, cutlines)
- `rich` / `typer` (wizard + CLI)
- `pyyaml` (patches later)

### 13.3 Notes
- Ensure GDAL/PROJ axis order behavior is explicitly managed (GDAL 3+).

---

## 14. Milestones (high level)

- **M0**: reference harvest + backend contracts  
- **M1**: DEM normalization (mosaic/reproject/resample/tile/fill) + Ortho4XP backend build  
- **M2**: DSF validation harness + triangle budget guardrails  
- **M3**: XP12 raster enrichment (seasons/soundscape)
- **M4**: AutoOrtho-ready output mode
- **M5**: installation correctness tooling (conflict detection + publish)

---

## 15. References (harvest targets)

> URLs are provided in code formatting so they can be copied directly.

### X‑Plane DSF / base mesh
- `https://developer.x-plane.com/article/dsf-usage-in-x-plane/`  
  **Pull:** DSF bounds properties, raster layer names (XP12 seasons/soundscape), compression notes.
- `https://developer.x-plane.com/article/understanding-and-building-dsf-base-meshes/`  
  **Pull:** base mesh constraints, physical mesh requirements.
- `https://developer.x-plane.com/tools/xptools/`  
  **Pull:** DSFTool usage patterns and tooling expectations.

### Ortho4XP + community custom DEM handling (how others solve our constraints)
- `https://forums.x-plane.org/forums/topic/156476-question-regarding-elevation-data-and-ortho4xp-config-file/`  
  **Pull:** community-stated custom DEM requirements (tile coverage, WGS84, nodata), and note about multi-resolution DEM refinement.
- `https://www.reddit.com/r/flightsim/comments/96t02m/managed_to_get_a_5m_mesh_working_with_ortho_in/`  
  **Pull:** practical preprocessing steps: mosaic → reproject → clip to 1×1 → export GeoTIFF for Ortho4XP.
- `https://forums.x-plane.org/forums/topic/161799-how-to-use-own-orthophotos/`  
  **Pull:** Ortho4XP tile naming/indexing for orthophotos; useful for AutoOrtho compatibility and our own “no-download imagery” modes.
- `https://forums.x-plane.org/forums/topic/112932-custom-hires-digital-elevation-model-mosaic/`  
  **Pull:** evidence that community DEM sources exist in ETRS89/UTM and require tiling/merging into 1×1 tiles.
- `https://forums.x-plane.org/forums/topic/291338-ortho4xp-tiles-epsg4326-wgs84/`  
  **Pull:** common projection misconceptions and how users think about EPSG:4326 vs EPSG:3857.
- `https://github.com/oscarpilote/Ortho4XP`  
  **Pull:** XP12 compatibility notes (v1.40+), config knobs, DEM ingestion behaviors.

### AutoOrtho
- `https://github.com/kubilus1/autoortho`  
  **Pull:** install expectations.
- `https://kubilus1.github.io/autoortho/latest/details/`  
  **Pull:** Ortho4XP naming conventions for `.dds`, how the VFS interception works, recommended Ortho4XP settings like `skip_downloads`.

### GIS/CRS handling (critical for ETRS89 support)
- `https://gdal.org/en/stable/programs/gdalwarp.html`  
  **Pull:** warp options for reprojection, resampling, cutlines, target extents.
- `https://gdal.org/en/stable/tutorials/osr_api_tut.html`  
  **Pull:** GDAL 3 axis-order behavior and `SetAxisMappingStrategy(OAMS_TRADITIONAL_GIS_ORDER)` guidance.
