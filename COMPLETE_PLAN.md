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

## Phase 12 — v0.1.1 Compatibility & Correctness Hotfix (done)
- Preserve DSFTool command lists end-to-end, including wrappers and `.py` script handling.
- Document tool command list semantics and quoting rules for Windows vs POSIX in the spec.
- Allow patch rebuilds to skip normalization when `tile_dem_paths` covers all target tiles.
- Enforce always_xy axis order for CRS transforms in tiling; include projected-CRS regression guidance.
- Suppress the misleading Ortho4XP multi-DEM warning when per-tile DEMs are supplied.
- Fix Ortho4XP runner PYTHONPATH injection to point at the repo `src/` root.
- Make Ortho4XP DEM staging deterministic by removing stale suffix variants and recording the staged path.
- Clarify DDSTool documentation to note it ships with XPTools but is not yet invoked.

## Phase 13 — Spec Alignment: Tile Inference + AOI + Wizard Inspect (planned)
- Implement tile inference from DEM bounds (and from AOI polygon bounds when provided).
  - Add `dem2dsf tiles --dem <path> [--aoi <path>]` helper.
  - Allow `dem2dsf build` to omit `--tile` when inference is enabled or when tiles can be inferred safely.
- Add `--aoi <geojson/shp>` support to `build` and `wizard`.
  - Support AOI masking of normalized tiles (in addition to DEM stack AOIs).
  - Record `inputs.aoi` in build_plan/build_report for provenance.
- Upgrade the wizard to match spec intent:
  - Inspect DEM(s): CRS, bounds, nodata, resolution, dtype, vertical units
  - Propose inferred tiles and per-tile coverage estimates
  - Surface early warnings for extreme resolutions, missing CRS, suspect elevation ranges, NaN/outlier prevalence, or unit mismatches
  - Offer recommended defaults based on inspection

## Phase 14 — Provenance, Reproducibility, and Determinism (done)
- Extend build_plan/build_report with provenance metadata (input fingerprints/hashes, toolchain paths/versions, Ortho4XP script + git commit when available, python deps, vertical-unit assumption, coverage summary).
- Add `--provenance-level {basic,strict}` and `--stable-metadata` (omit created_at).
- Add pinned versions config with override support and report version drift warnings.
- Update schemas/contracts, specs, and migration notes for optional timestamps and provenance blocks.

## Phase 15 — Validation & Quality Modes (planned)
- DSF validation levels:
  - `--dsf-validation {none,bounds,roundtrip}` (default: bounds or roundtrip as currently)
  - Optional parallel DSFTool validation with worker cap
  - Allow validate-only for tiles with warnings/errors unless `--validate-all`
- XP12 raster checks:
  - Clarify required vs best-effort rasters
  - Define “xp12-enhanced complete” requirements in spec and docs
  - Add `--xp12-strict` to fail the build when enrichment requirements are unmet
- AutoOrtho checks:
  - Split “invalid refs” vs “missing files”
  - Add `--autoortho-texture-strict` option
- DEM sanity checks:
  - Detect unrealistic elevation ranges, spikes, NaN prevalence, or unit issues
  - Detect missing CRS early with actionable guidance
- Semantic DSF validations:
  - Validate presence of expected properties/rasters (for xp12-enhanced)
  - Add golden fixtures for DSF2Text parsing regression tests
- Better reporting:
  - Per-tile reason codes for warnings/errors
  - Include exact runner command used plus Ortho4XP cfg diff (unless sensitive)
- Optional DDSTool integration (if kept):
  - DDS header/format validation for packaged textures
  - Fail/warn policy controls

## Phase 16 — Performance & Scale (done)
- Avoid in-memory per-tile merges for multi-source tiles (streaming merge to disk, GDAL VRT + Warp/VRT where appropriate).
- Reduce redundant I/O in normalization:
  - windowed coverage metrics
  - combine fill + metric computation where possible
  - compute coverage metrics from in-memory arrays during fill when possible
  - apply backend profile mapping during write/warp rather than re-opening files
  - document `--skip-coverage-metrics` as a performance knob (and defaults)
- Improve concurrency safety and throughput:
  - document GDAL thread caveats
  - consider process-based parallelism for heavy raster steps
  - document `--tile-jobs 0` mode and safe ranges
- Cache improvements:
  - optional SHA-256 cache validation
  - per-tile cache reuse when tile lists change
- Optional compression for intermediate tiles (GeoTIFF LZW/DEFLATE) to reduce disk usage.
- Add “big build” guardrails:
  - expected disk usage / RAM warnings
  - warn when expected output array sizes exceed a threshold
  - triangle explosion warnings based on resolution + tile count
- Reconcile `docs/references/file_formats.md` VRT mosaic mention with current GeoTIFF mosaic behavior (implement VRT mosaics or update docs).

## Phase 17 — Packaging & Distribution Improvements (done)
- Publish modes:
  - `publish --mode scenery` (essentials only)
  - `publish --mode full` (current behavior)
  - Define publish packaging spec (scenery-only vs full, manifest/audit contents, diagnostics inclusion defaults)
- Improve manifest/audit clarity:
  - record DSF compression status, tool versions used for packaging
  - optionally include build_plan/build_report (scenery mode can include or exclude)
- Release artifacts clarity:
  - document what GUI bundles include/exclude
  - provide portable config examples and templates
- End-user install ergonomics:
  - `pipx` guidance
  - clearer tool discovery examples (`tools/tool_paths.json` templates)
  - platform-specific quickstart pages
- Compatibility spec:
  - supported OSes, Python versions (3.13+), and external tool version policy
- Security posture:
  - document archive/tool download trust assumptions
  - ensure archive extraction remains safe (even under future refactors)

## Phase 18 — DX, CI, and Integration Hardening (done)
- Expand CI:
  - separate unit vs e2e vs integration jobs
  - optional self-hosted integration job with Ortho4XP/XPTools available
  - tool-optional integration test matrix with explicit skips when tools are missing
- Add regression tests for critical edge cases:
  - DSFTool wrapper command lists (doctor + build validation parity)
  - patch rebuild with multi-DEM base plans and dem_stack inputs
  - CRS axis-order correctness in tiling (always_xy)
  - Ortho4XP runner env path resolution (`_runner_env` source_root)
  - DEM staging cleanup when suffix changes
  - backend multi-DEM warning suppression when `tile_dem_paths` is present
- Add integration smoke tests (auto-skip when tools are missing):
  - DSFTool `dsf2text` + `text2dsf` roundtrip on a tiny fixture
  - Ortho4XP single-tile build with a tiny DEM
  - XP12 enrichment smoke against a known Global Scenery sample (if feasible)
- Expand end-to-end CLI coverage:
  - `build` with inferred tiles (when implemented)
  - `build --aoi ...` (when implemented)
  - `publish --mode scenery` vs `publish --mode full` (when implemented)
- Add perf trend tracking:
  - baseline comparisons in CI (warn on regressions)
  - store environment metadata for each perf run
- Optional: add static typing gates (mypy/pyright) and expand ruff rules (beyond E/F/I).

## Phase 19 — Workflow & UX Improvements (done)
- Resume / incremental builds:
  - `--resume` skips tiles already built and validated
  - `--resume validate-only` re-runs checks without rebuilding
- Config-file driven builds:
  - `dem2dsf build --config build.json` for tiles, DEMs, options, and tools
  - Produce a locked config snapshot for reproducibility
- More informative `doctor` output:
  - actionable install guidance for each missing tool
  - print detected Ortho4XP cfg overlay source and recommended values
- Better defaults and “sane presets”:
  - propose target resolution based on DEM resolution
  - warn when extremely fine resolution risks triangle explosion
- CLI UX: tool command ergonomics:
  - make `--dsftool` and `--runner` consistent command lists everywhere
  - add `--dsftool-path` shorthand for the simple case
- Output directory hygiene:
  - define output folder layout (normalized, runner_logs, validation, diagnostics, etc.)
  - add `dem2dsf clean --build-dir ...` to remove caches/logs selectively
- GUI improvements:
  - tile inference button (from DEM bounds)
  - validate inputs before starting
  - show expected disk usage estimates and time warnings
- Better warnings:
  - when coverage is low, explain likely outcomes and next actions (fallback DEM, adjust AOI, etc.)

## Phase 20 — Extensibility & Protocols (planned)
- Formal plugin interfaces:
  - backend discovery via entrypoints
  - overlay generator plugins via stable interface with versioning
- Runner protocol versioning:
  - define a JSON schema for runner events
  - persist events into diagnostics bundle in a stable format
- Centralize coordinate transforms:
  - route all bounds transforms through `dem2dsf.dem.crs.transform_bounds()` (always_xy)
  - consolidate CRS utilities into a single module/policy

## Reference Map (BUGS_ENHANCEMENTS.md)
- Release notes claim DDSTool support: `docs/release_notes.md:8-13`
- CLI `--dsftool` is a command list: `src/dem2dsf/cli.py:205-209`
- Build truncates tool commands to the first token: `src/dem2dsf/build.py:108-114`
- DSFTool wrapper only accepts `Path`: `src/dem2dsf/tools/dsftool.py:26-44`
- Patch forces `normalize=false` then calls `run_build` with base DEM list: `src/dem2dsf/patch.py:230-241`
- Build rejects `normalize=false` unless exactly one DEM: `src/dem2dsf/build.py:262-268`
- Spec requires axis order safety and tile inference: `dem2dsf_xp12_spec_v0_2.md:134-146`
- Tiling uses rasterio transform_bounds directly: `src/dem2dsf/dem/tiling.py:37-42`
- Repo has always_xy transform helper: `src/dem2dsf/dem/crs.py:17-29`
- Ortho backend misleading multi-DEM warning: `src/dem2dsf/backends/ortho4xp.py:93-100`
- Runner PYTHONPATH injection uses a likely-wrong parent path: `src/dem2dsf/runners/ortho4xp.py:192-202`
- Ortho4XP DEM staging does not remove stale suffix variants: `src/dem2dsf/tools/ortho4xp.py:110-115`
- Build plan lacks checksums/tool versions by default: `src/dem2dsf/reporting.py:17-38`
