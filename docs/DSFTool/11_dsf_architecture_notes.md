# DSF architecture notes (what matters when using DSFTool)

This note condenses a few points from Laminar’s DSF file format specification that are useful when you’re building DSFTool-based tooling.

## DSF tile scope

DSF files represent a **1×1 degree** section of a planet (usually Earth).

Source: https://developer.x-plane.com/article/dsf-file-format-specification/

## Coordinates and projection

Laminar’s DSF spec describes:

- horizontal coordinates in **degrees lat/lon**
- vertical in **meters MSL**
- Earth approximated as **WGS84**
- coordinates stored as **fixed point integers** scaled/offset by floats (math done in 64-bit floats)

Source: https://developer.x-plane.com/article/dsf-file-format-specification/

**Practical impact:** be very careful about float formatting and rounding if your generator tries to “stitch” meshes; equality is often bit-level once quantized.

## DSF compression reality

The DSF file format spec notes:

- DSF files are not internally compressed
- clients may support compressed wrappers; the cookie at the beginning can identify compressed vs uncompressed formats (e.g., `XPLANE` vs `PK`/`7Z`)
- X‑Plane 10 supports 7Z-compressed DSFs; X‑Plane 9 does not

Source: https://developer.x-plane.com/article/dsf-file-format-specification/  
(Also see DSF usage doc: https://developer.x-plane.com/article/dsf-usage-in-x-plane/)

## Hashing / cache invalidation

The DSF spec states DSF files carry a 128-bit **MD5 hash** at end describing file contents to detect modification and rebuild caches as needed.

Source: https://developer.x-plane.com/article/dsf-file-format-specification/

**Practical impact:** if you modify DSFs via DSFTool, the rebuilt DSF should have a new hash automatically (DSFTool writes DSF correctly). If you ever write DSF binaries yourself, you must handle this.

## DSF as “atoms + commands”

The spec describes DSF as a chunky/atomic container with:

- **atom sections** (chunk headers with IDs and lengths)
- **definition tables** (ordered lists → index references)
- **point pools** (N-dimensional coordinate pools with scale/offset)
- a **command stream** that sets state and instantiates scenery primitives

Source: https://developer.x-plane.com/article/dsf-file-format-specification/

DSFTool’s DSF2Text format intentionally hides most of the atom/pool machinery — but it still preserves the **definition index model**, and `DIVISIONS`/`HEIGHTS` give you limited control over how DSFTool creates pools.

## Raster layers in DSF

The DSF spec documents raster layers as part of the DSF container starting with X‑Plane 10, while the DSF usage doc defines how X‑Plane interprets raster names like `elevation`, `sea_level`, `soundscape`, etc.

Sources:

- Spec-level: https://developer.x-plane.com/article/dsf-file-format-specification/
- Behavior-level: https://developer.x-plane.com/article/dsf-usage-in-x-plane/

