# 08 — Failure modes & resilience strategies (for robust wrappers)

This is the “support burden reducer” doc: the more of this you automate, the fewer confused users you’ll have.

## 1) Python / dependency mismatch

### Symptom
- missing modules (`pyproj`, `rtree`, etc.)
- Ortho4XP failing on newer Python versions
- build issues for compiled extensions (e.g., scikit-fmm)

### Notable constraint
A GitHub issue explicitly states that as of Sep 2024 Ortho4XP required `numpy < 2`, and that `numpy < 2` only supports Python up to 3.10—so users may need Python 3.10.

Wrapper strategies
- ship a self-contained runtime or provide a validated installer
- run a startup “environment doctor” that checks:
  - Python version
  - numpy, pyproj, shapely, rtree, pillow, requests, (optional) scikit-fmm
- store environment versions in your run logs

## 2) “MultiPolygon object is not iterable” / vector assembly errors

### Symptom
- fails right at “Assemble Vector Data”
- popup: `TypeError: 'MultiPolygon' object is not iterable`

Wrapper strategies
- offer a “purge OSM cache for this tile” action
- support retry with updated dependencies (Shapely changes can cause geometry edge cases)
- emit a minimal reproduction bundle: tile coords + tile cfg + log + cache hashes

## 3) Triangle4XP failures (mesh triangulation)

### Symptom patterns
- errors mentioning tiny triangles / finite precision
- “Try increasing the area criterion and/or reducing the minimum allowable angle…”
- triangulation crashing more often on some platforms (reports: MSVC build differences)

Wrapper strategies (auto-retry ladder)
1) first retry: reduce `min_angle` (e.g., 10 → 5)
2) second retry: reduce `min_angle` further (→ 0)
3) third retry: adjust “area criteria” knobs (increase `min_area`, reduce overly aggressive constraints)
4) last resort: reduce problem-causing vector features (e.g., temporarily lower `road_level`)

Also:
- log the “final number of constrained edges” and triangle count; these correlate with failure risk.
- keep all intermediate artifacts so retries don’t redo downloads unnecessarily.

## 4) Missing overlay output or “Earth nav data … absent”

### Symptom patterns
- overlay DSF absent
- Ortho4XP message reminding you the overlay source directory must be set first

Wrapper strategies
- validate `custom_overlay_src` exists and contains `Earth nav data`
- pre-create `yOrtho4XP_Overlays/Earth nav data/<bucket>/`
- after extraction, verify DSF exists for the tile; if not, fail the run as “overlay incomplete”

## 5) Version skew between cfg and code (“unknown parameter” class of errors)

### Symptom patterns
- stack trace mentions missing attributes like `lane_width`
- tile cfg saved with parameters not supported by the installed Ortho4XP build

Wrapper strategies
- when loading a cfg, validate supported keys against the actual Ortho4XP build
- offer an automatic “cfg migration” step:
  - drop unknown keys with warnings
  - suggest upgrading Ortho4XP build when important keys are missing

## 6) WMS / provider issues (imagery download failures)

### Symptom patterns
- server expects WMS 1.1.1 but client uses 1.3.0
- massive slowdowns when using WMS vs tile servers

Wrapper strategies
- treat providers as plug-ins with health checks
- for WMS:
  - allow setting `wms_version`
  - keep chunk sizes reasonable
  - prefer EPSG:3857 when available to reduce warping
- if imagery is missing, fail step 3 with an actionable reason, not as a generic crash

## 7) File permission / path issues

### Symptom patterns
- “Cannot create tile subdirectories”
- rename errors when activating DSFs
- failures on external drives or file systems with odd permissions/semantics

Wrapper strategies
- run a preflight check:
  - create/delete test file in base folder
  - check free space
- normalize all paths and avoid ambiguous trailing separators
- on Windows: be careful with long paths and permission elevation
