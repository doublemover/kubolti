# COMPLETE_PLAN

Status legend: planned | in-progress | done. Update the status tags as work lands. This document supersedes all prior plan docs.

## Phase 0 — Runway Cleanup (Ortho4XP-only pivot) (done)
- Remove the legacy backend, tooling, and CLI/GUI flags.
- Simplify installers/build scripts to Ortho4XP + XPTools (DSFTool/DDSTool) only.
- Update specs/backlog/docs to reflect the Ortho4XP-only pipeline.
- Prune legacy backend tests and replace with Ortho4XP-focused coverage.
- Add a postmortem apology letter in docs.

## Phase 1 — Ortho4XP Reliability Pass (done)
- Add explicit Ortho4XP version and Python runtime checks in `doctor`/runner.
- Strengthen runner validation and error messages for missing configs.
- Add integration tests that auto-skip when Ortho4XP or XPTools are absent.

## Phase 2 — Tooling & Distribution Polish (done)
- Tighten `install_tools.py` UX (clearer output, no dead flags).
- Refresh `tool_urls.json` via the updated fetcher and document update steps.
- Review release docs to ensure Ortho4XP-only assumptions are clear.

## Phase 3 — Usability & Observability (done)
- Expand GUI guidance for Ortho4XP runner options (batch, python path).
- Add a small diagnostics bundle script for build reports + perf metrics.
- Fill any remaining Ortho4XP-only test gaps and re-check coverage.

## Phase 4 — Correctness Passes (done)
- Fix DSF path layout to use X-Plane 10×10 bucket folders everywhere.
- Centralize tile/bucket path logic and replace per-tile folder assumptions.
- Correct XP12 raster enrichment to include raw raster sidecars.
- Add integration coverage for XP12 enrichment with DSFTool outputs.

## Phase 5 — High-impact Fixes (done)
- Publish `--dsf-7z` as compressed `.dsf` (optional backup of uncompressed).
- Apply density presets to Ortho4XP config with safe patch/restore.
- Fix Custom Scenery scan to use DSF filename for tile id.
- Re-evaluate XPTools pin/version guidance for XP12-era DSFs.

## Phase 6 — Performance & Scale (done)
- Reduce mosaic memory usage (VRT or chunked merge).
- Add normalization cache reuse keyed by inputs/params.
- Parallelize per-tile workflows safely.
- Replace XP12 global DSF `rglob` fallback with bucket path lookup.

## Phase 7 — Maintainability & DX (done)
- Align Ortho4XP DEM staging with Elevation_data buckets + N/S/E/W naming. (done)
- Preserve tile cfg files alongside build outputs for provenance. (done)
- Add dedicated X-Plane path helpers + tests for bucket logic. (done)
- Replace `print()` with structured logging (`--verbose/--quiet`), per-tile logs. (done)
- Refactor CLI option wiring into shared helper/dataclass. (done)
- Add Ortho4XP overlay source validation + scenery ordering helper. (done)
- Parse Ortho4XP runner logs into structured milestone events. (done)
- Add cache path controls and cleanup for Ortho4XP caches. (done)
- Implement Triangle4XP retry ladder (min_angle/area) in runner. (done)

## Phase 8 — E2E + Integration Hardening (done)
- Ensure CLI subprocess tests inject repo `src/` into `PYTHONPATH`.
- Harden integration runner tests to use stable env configuration.
- Keep e2e/integration skips explicit when external tools are missing.

## Phase 9 — Performance Baselines (done)
- Add environment metadata to perf summaries for baseline context.
- Document perf baseline metadata in benchmarking docs.

## Phase 10 — GUI/Test Polish (done)
- Validate GUI tile input and surface invalid tile errors early.
- Add focused GUI test coverage for tile validation.

## Phase 11 — Release Automation (done)
- Build GUI bundles on release workflow for all OS targets.
- Attach GUI bundles to tagged releases and update release docs.

## Completed Archive (legacy plans)
### Core phases from `docs/plan_remaining.md` (done)
- Phase A: README polish and roadmap updates.
- Phase B: coverage strategies and normalization guardrails.
- Phase C: DSFTool validation + bounds checks.
- Phase D: wizard prompt expansion and defaults.
- Phase F: 7z packaging and tool discovery prompts.
- Phase H: E2E CLI coverage for build/publish/patch/overlay.
- Phase I: release packaging + tool discovery.
- Phase J: overlay remix + sample pipelines.
- Phase K/M/P: profiling, perf CI, and baseline trends.
- Phase L/O: preset library + import/export.
- Phase N/R/S: GUI polish, preferences, and CI bundles.

### Bonus phases from `docs/plan_bonus.md` (done)
- BONUS-001: multi-resolution DEM stacks.
- BONUS-010: patch-first workflow.
- BONUS-020: draped imagery overlays.
- BONUS-030: overlay plugins.
- BONUS-040: GUI front-end.

### Baseline backlog from `dem2dsf_feature_backlog_v0_2.md` (done)
- Foundations, DEM normalization, Ortho4XP backend, DSFTool validation.
- Wizard flow, XP12 raster checks/enrichment, triangle guardrails.
- AutoOrtho compatibility/presets, publishing/packaging.
