# Ortho4XP Own Orthophotos Forum Thread

Source: https://forums.x-plane.org/forums/topic/161799-how-to-use-own-orthophotos/

## Why it matters
Spec v0.2 cites this thread for Ortho4XP tile naming and orthophoto handling conventions.

## Key points
- To reuse manually downloaded imagery with a provider like "GO", pre-process so the extent matches the provider tile indexing scheme.
- Ortho4XP assembles 16x16 tiles of 256x256 pixels into a 4096x4096 texture; name uses the top-left tile index: {tile-y}_{tile-x}_{provider}{zoom}.jpg.
- Example grouped path: `./Orthophotos/+40+000/+45+007/45552_68080_GO17.jpg`.
- Alternative: serve orthophotos via WMS (QGIS Server/OSGeoLive) and point Ortho4XP to the WMS URL.
- gdal_warp + gdal_translate can reproject to WebMercator and split into 4096x4096 chunks on the right tile index.

## Gotchas
- Incorrect tile boundaries or naming will prevent reuse; align to provider tile boundaries before renaming.
- Large source images often need splitting; Ortho4XP expects the 4096x4096 chunks it assembles from 256x256 tiles.
