# DSFTool research notes (design, use, enhance)

This zip contains a set of markdown notes focused on **DSFTool** (Laminar Research / X‑Plane), with an emphasis on:

- how DSFTool is intended to be used (toolchain role, limits)
- how to obtain the official binaries
- how to integrate it correctly in your own tooling (wrappers, generators)
- how DSFTool’s **DSF2Text** format works (commands, ordering rules, raster sidecars)
- common gotchas and troubleshooting patterns

## What’s inside

1. `01_what_dsftool_is_and_isnt.md`
2. `02_getting_dsftool_binaries.md`
3. `04_dsftool_cli_reference.md`
4. `05_dsf2text_text_format_reference.md`
5. `06_raster_layers_and_raw_files.md`
6. `07_7z_compressed_dsfs.md`
7. `08_merging_dsfs.md`
8. `09_troubleshooting_and_gotchas.md`
9. `10_design_notes_for_dsftool_based_generators.md`
10. `11_dsf_architecture_notes.md`
11. `99_sources_and_further_reading.md`

## Quick context

- DSFTool is part of the **XPTools** command‑line tool bundle and is used to convert **DSF ⇄ text**.
- DSF is a **container format** used by X‑Plane; it can store mesh, overlays, roads, polygons, objects, rasters, etc.
- DSFTool’s text format is **not** a 1:1 dump of DSF internals; it is a pragmatic editable/pipeable representation, mainly for **programmatic generation**.

> Note: Where possible, these notes cite Laminar’s official developer documentation and tool release notes.
