# Ortho4XP DEM Mosaic Forum Thread

Source: https://forums.x-plane.org/forums/topic/112932-custom-hires-digital-elevation-model-mosaic/

## Why it matters
Spec v0.2 cites this thread as evidence for mosaic workflows and multi-DEM inputs.

## Key points
- Custom mosaics are used to fix artifacts in existing 20m DEMs and to fill borders needed for 1x1 degree tiles.
- Global or continental DEMs can be lower resolution or have voids; mosaics blend multiple sources to reach higher detail.
- High-resolution DEMs can include spikes/bumps from buildings, bridges, and vegetation (first-return effects); these artifacts are hard to smooth.
- Example contributor data: Spain DEMs at 25m in ASC format, ETRS89/UTM zones 28-31, ~1700 files.
- The workflow emphasizes blending between sources to make transitions unnoticeable across tile borders.

## Gotchas
- High-res mosaics can amplify urban artifacts; expect extra cleanup or smoothing in cities.
- Border blending matters; visible seams undermine mesh quality even with good source data.
