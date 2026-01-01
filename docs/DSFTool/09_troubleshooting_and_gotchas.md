# Troubleshooting & gotchas

This is a “things that commonly go wrong” list when working with DSFTool and DSF2Text.

## 1) Lat/Lon order mistakes

In multiple parts of DSF/DSF2Text, the coordinate order is **longitude first, then latitude**.

Example: object placement coordinates are:

1. Longitude
2. Latitude
3. Heading
4. Optional MSL height (depending on sim/version and feature usage)

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Object Types and Coordinate Organization)

**Symptom:** Objects appear in the wrong place, end up out of tile bounds, or X‑Plane rejects placements.

**Mitigation:** Make your generator’s coordinate ordering explicit (e.g., name variables `lon`, `lat` and keep them in that order throughout).

## 2) Tile boundary properties (sim/west/south/east/north)

Laminar’s docs say DSFs must contain all four bounds as integer degrees.

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Bounding Box and Location Properties)

**Symptoms of wrong bounds:**

- X‑Plane may ignore the DSF or load it in unexpected places.
- Objects may be considered out of bounds and dropped.

**Mitigation:**

- Validate that tile bounds match the DSF path (e.g., `Earth nav data/+40-080/+41-079.dsf` corresponds to west=-80 east=-79 south=40 north=41).

## 3) Properties ordering when generating DSF2Text

DSFTool’s README calls out ordering constraints (especially if piping):

- emit `DIVISIONS`, `HEIGHTS`, and `PROPERTY` up front
- ensure `sim/west/south/east/north` come last after other properties

Source: XPTools `README.dsf2text` in https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

**Symptom:** DSFTool errors or creates DSFs with missing/incorrect metadata.

**Mitigation:** Centralize property emission so the ordering can’t accidentally drift.

## 4) Line endings / encoding issues

DSFTool’s README warns that incorrect line endings (e.g., from some macOS editors) can crash DSFTool.

**Mitigation:**

- Always write DSF2Text using LF line endings.
- Prefer UTF‑8 (ASCII subset is safest).
- Avoid “smart quotes” or locale-dependent formatting.

## 5) Missing or mismatched raster RAW files

If your DSF2Text contains `RASTER_DATA ... filename`, DSFTool expects that RAW file to exist and match:

- width/height
- bytes per pixel (`bpp`)
- scale/offset assumptions

**Mitigation:**

- Treat rasters as part of a single “compile unit”: write DSF2Text and its RAW sidecars into the same staging directory, then compile.
- Consider using relative paths in `RASTER_DATA` for portability (test your DSFTool build’s behavior).

## 6) 7z-compressed DSFs

Global scenery DSFs may be shipped in 7z-compressed form. Older DSFTool builds may fail to open them, while newer builds can read them directly.

Source:  
- DSF usage doc (7z compression): https://developer.x-plane.com/article/dsf-usage-in-x-plane/  
- DSFTool release notes: https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

## 7) Overlay DSF restrictions

Laminar’s DSF usage doc lists restrictions for overlays vs base meshes (e.g., overlays can’t contain mesh patches).

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Overlay DSF Restrictions)

**Mitigation:** Decide early whether you’re generating:

- an **overlay DSF** (objects/polygons/networks only), or
- a **base mesh DSF** (terrain patches + optional overlays)

and enforce that in your generator.

## 8) Geometry validity (base mesh rules)

If generating base meshes, Laminar documents strict mesh validity rules:

- the tile area must be fully covered by hard triangles
- no T‑junctions (triangles must meet vertex‑to‑vertex)
- etc.

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Data Validation → Base Mesh)

These rules are the #1 reason “it compiles” but renders or collides incorrectly.

