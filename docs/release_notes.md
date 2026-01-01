# Release Notes (Draft)

## Tag: v0.1.0

Note: this release republishes artifacts after workflow/CI fixes; feature
content matches the scope below.

### Highlights
- Ortho4XP-first build pipeline with runner orchestration and tile staging.
- XPTools validation support (DSFTool/DDSTool) plus XP12 raster checks.
- Diagnostics bundles (reports, logs, metrics, profiles) for shareable triage.
- Coverage thresholds/metrics and normalization cache reuse.
- GUI launcher with persisted preferences and updated runner controls.

### Changelog

#### Added
- Ortho4XP runner improvements: timeouts, retries, streaming logs, JSON events.
- `--bundle-diagnostics` to zip reports, logs, metrics, and profiles.
- Coverage thresholds/metrics controls in build and GUI.
- `ultra` density preset and mosaic strategy selection (full vs per-tile).
- Normalization cache reuse keyed by DEM inputs and parameters.
- GUI preferences persistence plus expanded runner controls.

#### Changed
- Ortho4XP config overrides restore by default; opt in to persist changes.
- Runner logs default to `<build>/runner_logs` with JSON event files.
- XP12 raster enrichment now preserves raw sidecar files.

#### Fixed
- XP12 DSF validation now uses DSF bucket paths for lookup.
- DEM tiling respects bucket layout and correct DSF tile naming.

#### Tooling
- Added headless GUI smoke test in CI (`scripts/gui_smoke.py`).
- Added `dem2dsf-ortho4xp` console script for the runner.

### Tooling and distribution
- Ortho4XP runner packaged as `dem2dsf-ortho4xp` console script.
- GUI bundles for Windows/macOS/Linux via `scripts/build_gui.py`.
- XPTools zip install support via `scripts/install_tools.py`.

### Notes
- Ortho4XP config overrides are restored by default; use persist config to keep them.
- Integration tests that require external tools auto-skip when tools are missing.
