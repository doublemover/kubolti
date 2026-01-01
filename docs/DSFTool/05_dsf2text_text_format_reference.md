# DSF2Text format reference (DSFTool text files)

This file summarizes the **DSFTool text format** described in the `README.dsf2text` shipped with XPTools.

It’s a **line-oriented command language**: one command per line.

## 1) File header

DSFTool text files begin with a standard X‑Plane text header. A typical header looks like:

```text
A
800  <freeform authoring string>
DSF2TEXT
```

After the header, commands follow.

## 2) Comments and forward compatibility

- Lines starting with **unknown keywords are ignored**.
- No DSFTool keywords start with `#`, so `# ...` is safe for comments.

Practical implication: if you build a generator, you can embed your own comments without breaking DSFTool.

## 3) Critical ordering rules

From the DSFTool README:

- For **pipelined input**: `DIVISIONS`, `HEIGHTS`, and `PROPERTY` must appear before all other commands.
- For all input types: the tile boundary properties `sim/east`, `sim/west`, `sim/north`, `sim/south` must come **last**, after other property/meta lines.

A robust generator should output in this order:

1. Header
2. Optional `DIVISIONS`
3. Optional `HEIGHTS`
4. All `PROPERTY` lines (except tile bounds)
5. Definitions (`*_DEF`)
6. Geometry/feature commands
7. Final 4 bound properties (`sim/west`, `sim/south`, `sim/east`, `sim/north`) as `PROPERTY ...`

## 4) Meta commands

### `DIVISIONS <n>`

Controls how DSFTool allocates point pools.

- More pools can increase coordinate accuracy.
- Default noted in README: 8 divisions → 16 point pools and about 2^-19 degrees lateral resolution.

### `HEIGHTS <scale> <minimum>`

Controls encoding scale/offset for height data in PATCH_VERTEX point pools.

Default per README: scale `1.0`, minimum `-32758.0` → 1 m steps, max height ≈ +32767 m.

### `PROPERTY <name> <value>`

Adds a DSF property (key/value string). X‑Plane uses properties for:

- tile bounds (`sim/west/south/east/north`)
- overlay flags (`sim/overlay`)
- exclusions (`sim/exclude_*`)
- object density requirements (`sim/require_*`)
- and more (see DSF usage doc)

## 5) Definition commands (index tables)

These establish **definition tables**. Order matters: index 0 is the first definition, then increments.

- `TERRAIN_DEF <file>`
- `OBJECT_DEF <file>`
- `POLYGON_DEF <file>`
- `NETWORK_DEF <file>`
- `RASTER_DEF <name>`

Notes:

- Include file extensions.
- Filenames may contain whitespace but it’s discouraged.
- The related definition is required before you reference it by index.

## 6) Base mesh commands (patches / primitives)

### `BEGIN_PATCH <terrain_index> <near_lod> <far_lod> <flags> <coord_count>`

Begins a terrain patch (mesh patch). The patch references a `TERRAIN_DEF` by index.

Flags from README (bitfield):

- `1`: “hard” patch (collision/physics)
- `2`: overlay patch (z-buffer offset)

`coord_count` is the number of coordinates per vertex for this patch.

X‑Plane typically expects at least:

1. lon
2. lat
3. elevation (meters)
4. normal X
5. normal Z

Then optional additional coordinates (e.g., ST).

### `BEGIN_PRIMITIVE <type>`

Types per README:

- 0 triangles
- 1 triangle strip
- 2 triangle fan

### `PATCH_VERTEX <coords...>`

Defines one vertex inside the current primitive.

Per README: first values are lon/lat degrees, elevation meters, and normal vector components.

### `END_PRIMITIVE` / `END_PATCH`

Terminate current primitive/patch.

## 7) Object placement commands

### `OBJECT <type> <lon> <lat> <rotation>`

Places an object of the given `OBJECT_DEF` index.

### Explicit elevation variants

- `OBJECT_MSL <type> <lon> <lat> <rotation> <elevation>`
- `OBJECT_AGL <type> <lon> <lat> <rotation> <elevation>`

These allow explicit height placement.

## 8) Road/network commands

Road segments are described with begin/shape/end commands; curved variants include bezier handles:

- `BEGIN_SEGMENT ...`
- `BEGIN_SEGMENT_CURVED ...`
- `SHAPE_POINT ...`
- `SHAPE_POINT_CURVED ...`
- `END_SEGMENT ...`
- `END_SEGMENT_CURVED ...`

(See the DSFTool README and DSF usage doc for semantic constraints and coordinate meanings.)

## 9) Polygon commands

Used for facades, forests, draped polygons, etc.

- `BEGIN_POLYGON <type> <param> [<coords>]`
- `BEGIN_WINDING`
- `POLYGON_POINT <lon> <lat> [<more coords>]`
- `END_WINDING`
- `END_POLYGON`

## 10) Raster layers

Raster layers are defined via `RASTER_DEF` and described via a `RASTER_DATA` record:

```text
RASTER_DATA version=<v> bpp=<bpp> flags=<flags> width=<w> height=<h> scale=<s> offset=<o> <filename>
```

Rules from README:

- The key/value fields must appear in that order.
- The filename points to a **binary RAW file** containing the raster pixels.

Raster *types* and semantics depend on X‑Plane version (see `06_raster_layers_and_raw_files.md`).

## 11) Airport-ID filtering (conditional overlay sections)

DSFTool supports a `FILTER <index>` directive that ties to properties named `sim/filter/aptid`.  
This enables sections of overlay DSFs that only apply if the scenery pack “owns” an airport ID.

## Sources

- DSFTool README (full command descriptions and release notes):  
  https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

- DSF usage (properties, raster layer meanings, validation rules):  
  https://developer.x-plane.com/article/dsf-usage-in-x-plane/

