# Design notes for DSFTool-based generators / pipelines

If you are building a tool that **generates or edits DSFs** using DSFTool, treat DSFTool as a “compiler” and DSF2Text as your intermediate representation.

This doc is opinionated and focuses on reliability and maintainability.

---

## 1) Treat DSFTool as a “compile step”

A robust pipeline usually looks like:

1. Generate a DSF2Text file + any referenced raster RAW files into a **staging directory**.
2. Invoke:
   ```bash
   DSFTool --text2dsf stage/tile.txt stage/tile.dsf
   ```
3. Validate:
   - run `DSFTool --dsf2text stage/tile.dsf stage/roundtrip.txt`
   - perform sanity checks (bounds, counts, etc.)
4. Copy final DSF into the target scenery pack structure.

This decouples your generator from DSF binary details and keeps the “compiler” behavior consistent.

---

## 2) Pick a minimum DSFTool version (feature gating)

DSFTool has a long version history. Key feature gates from release notes and blog posts:

- Raster layer support added in **2.0 (2012)** — required if you emit `RASTER_DEF/RASTER_DATA`
- Direct reading of **7z DSF** added in **2.2 (2020)**
- Support for **7-plane base mesh vertex commands** added in the 2020 toolchain (important for many Ortho4XP meshes)
- Support for **set_AGL attributes** (X‑Plane 11.50) called out in 2020 beta builds
- Auto-detection improvements for `DIVISIONS` / `HEIGHTS` in 2.3/2.4 era

Sources:

- DSFTool README in XPTools: https://files.x-plane.com/public/xptools/xptools_win_24-5.zip  
- 2020 beta build post: https://developer.x-plane.com/2020/09/command-line-tools-beta-builds/

**Practical recommendation:** if you can, standardize on a modern XPTools bundle (e.g., 2020+ for Ortho meshes; 2024+ if you care about newer auto behaviors).

---

## 3) Make outputs deterministic

Determinism matters when you want reproducible builds, caching, or regression tests.

Recommendations:

- Emit definitions (`*_DEF`) in a stable order.
- Emit `PROPERTY` in a stable order (with the required ordering rules).
- Use consistent float formatting (fixed decimals) for coordinates.
- Avoid locale-sensitive formatting (decimal commas, etc.).

The DSFTool release notes mention precision changes over time (e.g., moving to 9 digits), which is another reason to **pin tool versions** in CI.

---

## 4) Avoid absolute paths in generated DSF2Text (when possible)

DSFTool allows the `RASTER_DATA ... <filename>` field to point to a RAW file. Many tool outputs use absolute paths.

For portability and CI:

- Prefer writing raw files into the same staging folder as the DSF2Text file.
- Use relative paths in `RASTER_DATA` if your DSFTool build accepts them (test!).
- If you must use absolute paths, ensure the build system constructs them reliably on each OS.

---

## 5) Validate against X‑Plane’s semantic rules, not just “DSFTool compiled”

A DSF can “compile” but still violate X‑Plane rules, producing rendering glitches or physics issues.

Laminar’s DSF usage document provides validation rules you can implement as checks:

- Base mesh:
  - full coverage by hard triangles
  - no T-junctions (vertex-to-vertex only)
- Objects:
  - within tile bounds
  - heading in [0, 360)
- Polygons:
  - winding rules, no self-intersection, no zero-length edges
- Roads:
  - no reverse direction segments, junction rules, etc.

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Data Validation section)

---

## 6) Plan for XP12 raster + water behavior

If your tool generates meshes that must work well in X‑Plane 12:

- Understand `sea_level`/bathymetry semantics and how XP12 uses them (Laminar’s docs describe XP10/11/12 differences).
- Consider adding support for new XP12 rasters like `soundscape` and seasonal layers if your use case needs them.

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/

---

## 7) Capture DSFTool stderr/stdout and return codes

DSFTool uses stdout/stderr differently depending on conversion direction, especially for piped workflows.

Recommendations for wrappers:

- Always capture **stderr** and persist it to logs on failure.
- Treat non-zero exit codes as failures.
- Consider a timeout/kill strategy for huge DSFs (DSFTool can be slow).

---

## 8) Contribute upstream when you hit a tool limitation

Laminar’s 2020 post asked users to report tool bugs via the Scenery Tools bug report form.

Source: https://developer.x-plane.com/2020/09/command-line-tools-beta-builds/

If your enhancement is generally useful (e.g., better error messages, safer parsing), upstreaming can reduce your maintenance burden.

