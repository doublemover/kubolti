# 06 — Overlays & scenery ordering (where many “it doesn’t work” reports come from)

## Overlay extraction: what it is
Overlay extraction takes roads/autogen/forests/etc. from an existing scenery source and writes them into:
- `yOrtho4XP_Overlays/Earth nav data/.../*.dsf`

Without overlays, users commonly report:
- “no roads”
- “no buildings/autogen”
- “world looks empty”

## The `custom_overlay_src` setting (must be correct)
Community walkthroughs instruct setting `custom_overlay_src` to the default overlays found in:
- `.../X-Plane 11/Global Scenery/X-Plane 11 Global Scenery`
(or the equivalent XP12 Global Scenery folder)

Wrapper guidance:
- validate that the directory contains `Earth nav data/`
- validate that it corresponds to the user’s X‑Plane version (XP11 vs XP12)
- fail fast with “pick your overlay source” instead of generating broken overlays

## Scenery ordering rules (X‑Plane behavior)
X‑Plane loads scenery packs in `scenery_packs.ini` order:
- items at the top override items below

Official X‑Plane support docs say:
- custom airports / overlay scenery should be higher priority than global airports
- orthophotos / base meshes should be moved to the very bottom

A practical ordering for Ortho4XP-related packs is typically:
1) custom airports
2) Global Airports
3) overlays (e.g., `yOrtho4XP_Overlays`)
4) base meshes / orthos (e.g., `zOrtho4XP_...`)

Wrapper guidance:
- generate a “suggested scenery order” snippet users can copy/paste
- detect if Ortho tiles are above airports and warn (it causes airport issues)

## “One overlay pack for everything” vs per-tile overlays
Ortho4XP generally creates a single `yOrtho4XP_Overlays` pack that contains overlay DSFs for many tiles.
That makes it easier to manage than thousands of overlay packs.

Wrappers should:
- avoid creating per-tile overlay packs unless there’s a strong reason
- ensure overlay DSFs are written to the correct 10°x10° bucket folder under `Earth nav data`

## Common overlay extraction failures to detect
1) overlay source path is wrong
2) overlay DSF folder not created for a bucket (some users manually create it as a workaround)
3) file permission errors (especially on external drives or protected locations)

Suggested wrapper behavior:
- pre-create expected output directories
- validate filesystem permissions and free space
- on error, show the exact source/destination paths Ortho4XP tried to use
