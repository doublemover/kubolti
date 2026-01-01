# AutoOrtho Details (Approach)

Source: https://kubilus1.github.io/autoortho/latest/details/

## Why it matters
AutoOrtho defines texture naming and DSF and terrain expectations for streaming orthophotos.

## Key points
- AutoOrtho acts as a virtual file system for orthophoto textures, not a plugin hook.
- Imagery files are detected by the Ortho4XP naming convention {row}_{col}_{maptype}_{zoomlevel}.dds.
- X-Plane loads DSF tiles from Custom Scenery/Earth Nav Data around the aircraft; terrain files reference texture paths.
- DDS files include mipmaps; AutoOrtho fetches only the needed mip level and caches data.
- Ortho4XP can generate scenery without downloading imagery by setting skip_downloads = True.

## Gotchas
- Terrain files still need correct texture references; AutoOrtho only replaces the files at read time.
- Cache limits can affect in-flight streaming; document memory settings when integrating.
