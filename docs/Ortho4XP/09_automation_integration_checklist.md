# 09 — Automation & integration checklist (productionizing Ortho4XP runs)

Use this as a punchlist when turning Ortho4XP from “a script that runs on your machine” into “a reliable pipeline step”.

## A. Inputs & configuration
- [ ] Explicitly collect:
  - [ ] tile coordinates list
  - [ ] X‑Plane version target (11 vs 12)
  - [ ] overlay source path (`custom_overlay_src`)
  - [ ] imagery provider + zoom settings (+ any custom ZL zones)
  - [ ] DEM selection: default vs custom vs multi-DEM stack
- [ ] Save a *resolved* configuration manifest per tile:
  - [ ] tile cfg
  - [ ] provider metadata
  - [ ] DEM filenames / hashes
  - [ ] Ortho4XP + Triangle4XP versions

## B. Filesystem, caching, reproducibility
- [ ] Choose a clear directory strategy:
  - [ ] shared caches (OSM/DEM/imagery)
  - [ ] per-tile working dirs
  - [ ] final output dir(s)
- [ ] Implement deterministic path creation:
  - [ ] create expected bucket folders (`Earth nav data/+LL+LLL/`)
  - [ ] create overlay output bucket folders
- [ ] Provide safe cleanup:
  - [ ] “purge tile OSM cache”
  - [ ] “purge tile imagery cache”
  - [ ] “purge tile DEM cache”
  - [ ] “purge everything except finished tiles”

## C. Execution model
- [ ] Run Ortho4XP with:
  - [ ] streamed logs
  - [ ] structured milestone parsing (Step 1/2/2.5/3/overlay)
- [ ] Support resume:
  - [ ] detect if step outputs already exist and are valid
  - [ ] skip or redo steps based on a user policy (“rebuild mesh”, “reuse imagery”, etc.)
- [ ] Parallelization:
  - [ ] be careful with shared caches and global temp names
  - [ ] prefer process isolation or per-worker temp roots
  - [ ] rate-limit imagery provider downloads

## D. Validation of outputs
- [ ] Validate base tile:
  - [ ] `zOrtho4XP_.../Earth nav data/<bucket>/<tile>.dsf` exists
  - [ ] textures + terrain exist (not empty)
  - [ ] tile cfg present in output root
- [ ] Validate overlay (if requested):
  - [ ] `yOrtho4XP_Overlays/Earth nav data/<bucket>/<tile>.dsf` exists

## E. Resilience & auto-retry
- [ ] Detect Triangle4XP failure messages and apply a retry ladder (see doc 08)
- [ ] Detect provider download failures and:
  - [ ] retry with backoff
  - [ ] switch to alternate provider if user configured it
- [ ] Detect version skew and cfg key mismatches; prompt for upgrade or auto-migrate cfg

## F. User-facing UX that prevents common mistakes
- [ ] “Scenery ordering” helper:
  - [ ] generate a suggested `scenery_packs.ini` ordering snippet
  - [ ] explain that base meshes go at the bottom
- [ ] “Disk estimate” warning:
  - [ ] zoom level increases can multiply size rapidly
- [ ] “Preflight checklist” before run:
  - [ ] overlay source valid
  - [ ] write permissions OK
  - [ ] free disk space adequate
