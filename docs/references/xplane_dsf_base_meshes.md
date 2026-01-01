# Understanding and Building DSF Base Meshes

Source: https://developer.x-plane.com/article/understanding-and-building-dsf-base-meshes/

## Why it matters
Explains how DSF meshes are structured (layers, patches, physical mesh), which affects mesh generation and validation.

## Key points
- Mesh is layered by terrain definitions; draw order is file order, and duplicate terrain definitions create separate layers.
- Patches are groups of triangles with shared properties; keep patches localized to avoid wasted drawing.
- Physical mesh is built from patches flagged physical; for any horizontal location, exactly one triangle must exist (no overlaps or holes).
- Physical mesh can be composed across layers, not necessarily a single layer.
- Overlay flag is used to avoid z-thrash when layers overlap.

## Gotchas
- Overlay patches still need correct texture coordinate counts; too few coordinates can crash X-Plane.
- Borders and masking require overlay flag and extra texture coordinates; plan mesh topology accordingly.
- Physical flag choice affects wet or dry physics where layers overlap.
