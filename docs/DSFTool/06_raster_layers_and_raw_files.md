# Raster layers and RAW files (elevation, sea_level, soundscape, seasons)

This note focuses on how DSF **raster layers** work in practice, and what DSFTool expects in DSF2Text.

## 1) Raster layers supported by X‑Plane (names + sim versions)

From Laminar’s “DSF Usage In X‑Plane” document, these raster DEM names are recognized:

- `elevation` — MSL elevation (X‑Plane 10+)
- `sea_level` — bathymetric depth / sea-floor info (X‑Plane 11+, semantics differ by version)
- `soundscape` — sound codes (X‑Plane 12)
- `spr1/spr2/sum1/sum2/fal1/fal2/win1/win2` — seasonal day-of-year layers (X‑Plane 12; all 8 must be present)

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Raster Layers table)

## 2) DSFTool support timeline (high level)

From DSFTool release notes (`README.dsf2text` shipped with XPTools):

- DSFTool 2.0 (2012) — added raster layer read/write for X‑Plane 10
- DSFTool 2.2 (2020) — can directly read 7z-compressed DSFs
- DSFTool 2.3/2.4 (2023–2024) — more auto-detection of `DIVISIONS` / `HEIGHTS` in certain conversions

Source: XPTools `README.dsf2text` inside https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

## 3) How meshes interact with elevation rasters

From the DSF usage spec:

If an **elevation** raster is present, X‑Plane will use it for a mesh vertex if:

- the patch vertex elevation is **-32768.0**, or
- the vertex’s terrain type is **water**

Additionally, if elevation raster data is present, normal vectors can be left as 0.0 and X‑Plane can compute them from the raster.

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Raster Data and Meshes)

### Practical implication for tool authors

If you are generating a base mesh and want good compression:

- Use raster DEM for most interior land vertices (set vertex elevation to -32768.0 so the raster supplies height).
- Consider explicit elevation for water/coastline vertices if you need a water-tight seal and stable water elevation behavior (Laminar notes their v10 global DSFs typically do this).

## 4) Bathymetry / sea_level semantics by simulator version

Laminar’s DSF usage document describes a version-dependent meaning for water “depth” vs bathymetry:

- XP10: depth is a literal depth value
- XP11: if bathymetry raster is present, the “depth” vertex coord can be a flag (0 coastline, 1 use bathymetry)
- XP12: with bathymetry present, the “depth” value becomes a **ratio** for interpolation (0 = ground elevation, 1 = bathymetry sample)

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Bathymetric Data table)

### Community caution about XP11 vs XP12

A long-running community theme is that XP11 didn’t fully use bathymetry data, while XP12’s 3‑D water and visible sea floor make it important. One example discussion:

- https://forums.x-plane.org/forums/topic/270403-dsf-raster-definitions-sea_level-bathymetry-and-the-future/

Treat forums as experiential guidance; prefer Laminar’s official docs for authoritative semantics.

## 5) DSFTool text representation of rasters

In DSF2Text:

1. Declare a raster layer name (e.g. `elevation`) via `RASTER_DEF elevation`
2. Provide a `RASTER_DATA ... <filename>` record that points to a **RAW binary** file.

The `RASTER_DATA` record includes:

- `version`
- `bpp` (bytes per pixel)
- `flags`
- `width`, `height`
- `scale`, `offset`
- and a filename

DSFTool expects the key/value properties in *exact order*.

Source: XPTools `README.dsf2text` inside https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

### Example RASTER_DATA lines (illustrative)

A forum post shows example output like:

- elevation raster: `bpp=2`, `scale=1.0`, `offset=0.0`, width/height around 1201
- sea_level raster: `bpp=2`, `scale=1.0`, `offset=0.0`, width/height around 256

(Example: https://forums.x-plane.org/forums/topic/270403-dsf-raster-definitions-sea_level-bathymetry-and-the-future/)

Use these as *examples only* — your raster geometry must match what your DSF expects.

## 6) Soundscape raster codes (XP12)

Laminar documents the `soundscape` codes (0=barren, 30=water, 40=forest, … up to 120=industrial).

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Sound Raster Data)

## 7) Seasonal raster requirements (XP12)

Laminar states:

- XP12 uses 8 seasonal raster files, and **all eight must be present**.
- Values represent “days since Jan 1”; seasons can wrap around year end.

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (Seasonal Data)

