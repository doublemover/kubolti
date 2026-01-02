# DEM2DSF (kubolti)
![CI](https://github.com/doublemover/kubolti/actions/workflows/ci.yml/badge.svg)
![coverage](https://img.shields.io/badge/coverage-93%25-brightgreen)

<p align="center">
  <img width="256" height="256" alt="logo" src="https://github.com/user-attachments/assets/d13fa407-6cea-44dc-902f-e4ef51ee69a8" />
</p>

DEM2DSF is a CLI-first pipeline that turns GeoTIFF DEMs into X-Plane 12 base-mesh
DSF tiles. It normalizes DEMs, orchestrates Ortho4XP builds, and validates the
output with DSFTool plus optional XP12 raster enrichment.

Feature requests are encouraged and welcome. If you want something, open an
issue with: (1) the goal, (2) sample inputs or constraints, (3) expected
outputs, and (4) any gotchas you already know.

## Quickstart

```bash
python -m venv .venv
python -m pip install -e .
dem2dsf --help
```

## Install options

- Venv (above) keeps everything inside the repo.
- pipx for an isolated CLI install:

```bash
pipx install .
```

## Documentation

- `docs/README.md` for the full documentation map.
- `docs/compatibility.md` for supported platforms and tool version policy.
- `docs/Ortho4XP/README.md` for Ortho4XP workflow notes and automation checks.
- `docs/DSFTool/README.md` for DSFTool usage and gotchas.
- `docs/build_config.md` and `docs/output_layout.md` for config files and build output layout.
- `docs/presets.md`, `docs/dem_stack.md`, and `docs/patch_workflow.md` for
  presets, DEM stacks, and patch workflows.
- `docs/quickstarts/` for platform-specific setup steps.
- `docs/security_posture.md` for download/extraction trust assumptions.

## Current capabilities

- DEM normalization pipeline (mosaic, reprojection, tiling, fill strategies)
  with cache reuse and coverage metrics.
- Ortho4XP runner orchestration with config overrides, retries, timeouts, and
  per-tile logs plus optional config persistence.
- DSFTool validation (roundtrip or bounds) plus optional DDS validation via
  DDSTool, and XP12 raster inventory with optional enrichment from Global Scenery.
- Density presets and triangle guardrails (including the ultra preset).
- AutoOrtho compatibility checks for texture references.
- Publish packaging with optional DSF 7-Zip compression and backups.
- Overlay generation, patch workflows, Custom Scenery scans, and cache tools.
- Config-driven builds, resume/validate-only runs, and clean command for cached artifacts.
- Tkinter GUI for build and publish with persisted preferences.

## Roadmap highlights

See `COMPLETE_PLAN.md` for the full sequence. Highlights:
- Tighten Ortho4XP presets and AutoOrtho ergonomics.
- Improve XP12 validation coverage and diagnostics.
- Expand integration and end-to-end coverage with performance profiling.

## External tools and discovery

DEM2DSF orchestrates external tools you provide:
- Ortho4XP: https://github.com/oscarpilote/Ortho4XP (target baseline 1.40)
- XPTools: https://developer.x-plane.com/tools/xptools/ (DSFTool, DDSTool)
  - DSFTool 2.2+ is required to read 7z-compressed DSFs directly.
- Optional: 7-Zip for DSF compression.

Tool discovery loads `tools/tool_paths.json` from the repo or current working
folder, or an explicit file set in `DEM2DSF_TOOL_PATHS`.
See `docs/tool_paths.template.json` for a portable template.

Install/build helpers:

```bash
python scripts/install_tools.py --write-config
```

XPTools (DSFTool/DDSTool) are pulled from the platform zip on the tools page.
Use `--xptools-url` or `--xptools-archive` to override the download.

## Usage guide (by purpose)

Tip: after install you can run either `dem2dsf ...` or `python -m dem2dsf ...`.

### Build tiles

```bash
dem2dsf build --dem dem.tif --tile +47+008 --output build
```

Build outputs include `build/build_plan.json`, `build/build_report.json`, and
`build/build_config.lock.json`.
Use `--tile-jobs 4` to parallelize per-tile normalization work.

Infer tiles (explicit opt-in) and apply an AOI mask:

```bash
dem2dsf build --dem dem.tif --infer-tiles --aoi area.geojson --output build
```

Use `--aoi-crs EPSG:4326` if your AOI lacks embedded CRS metadata. WGS84 is the
preferred CRS.

### Config-driven builds

```bash
dem2dsf build --config build.json --output build
```

The config file can provide `inputs`, `options`, and `tools` overrides. CLI
flags take precedence over config values.

### Resume builds

```bash
dem2dsf build --output build --resume
dem2dsf build --output build --resume validate-only
```

`--resume` skips tiles already marked `ok` in `build_report.json`. Use
`validate-only` to rerun validations without rebuilding.

### Infer tiles

```bash
dem2dsf tiles --dem dem.tif --aoi area.geojson --json
```

### AutoOrtho mode

```bash
dem2dsf autoortho --dem dem.tif --tile +47+008 --ortho-root C:/Ortho4XP
```

You can also use `dem2dsf build --autoortho` to enable AutoOrtho checks.

### Wizard (CLI)

```bash
dem2dsf wizard --dem dem.tif --tile +47+008 --output build --defaults
```

Add `--infer-tiles` to let the wizard propose tiles from DEM/AOI bounds, and
`--aoi area.geojson` to mask tiles before the backend runs.

### Logging

Use `--verbose`, `--quiet`, `--log-json`, or `--log-file path.json` to tune CLI
logging. Ortho4XP runner logs are written under `build/runner_logs/` with
`.stdout.log`, `.stderr.log`, `.events.json`, `.config.json`, and the main
`.run.log` per tile.

### Coverage and diagnostics

```bash
dem2dsf build --dem dem.tif --tile +47+008 --output build \
  --min-coverage 0.95 --coverage-hard-fail --bundle-diagnostics
```

### Validation and XP12 enrichment

```bash
dem2dsf build --dem dem.tif --tile +47+008 --output build \
  --quality xp12-enhanced --dsftool /path/to/DSFTool \
  --global-scenery "X-Plane 12/Global Scenery" --enrich-xp12
```

Optional validation flags:

```bash
dem2dsf build --dem dem.tif --tile +47+008 --output build \
  --dsf-validation roundtrip --dsf-validation-workers 4 --validate-all

dem2dsf build --dem dem.tif --tile +47+008 --output build \
  --dds-validation ddstool --ddstool /path/to/DDSTool --dds-strict
```

### Publish artifacts

```bash
dem2dsf publish --build-dir build --output build.zip --dsf-7z
```

Use `--mode scenery` to include only the X-Plane scenery essentials
(`Earth nav data`, `terrain`, `textures`) plus build plan/report metadata.

Add `--dsf-7z-backup` to keep `.dsf.uncompressed` backups or
`--sevenzip-path <path-to-7z>` to override detection.

### Patch and overlay

```bash
dem2dsf patch --build-dir build --patch patch_plan.json --output patched

dem2dsf overlay --build-dir build --output overlay
```

### Scenery scan and cache

```bash
dem2dsf scan --scenery-root "X-Plane 12/Custom Scenery"

dem2dsf cache list --ortho-root "C:/Ortho4XP" --tile +47+008
dem2dsf cache purge --ortho-root "C:/Ortho4XP" --tile +47+008 --confirm
```

### Clean build artifacts

```bash
dem2dsf clean --build-dir build
dem2dsf clean --build-dir build --include normalized --include runner-logs --confirm
```

### Presets

```bash
dem2dsf presets list
dem2dsf presets show ultra
dem2dsf presets export --output my_presets.json
dem2dsf presets import my_presets.json
```

### GUI

```bash
dem2dsf gui
```

Preferences are stored at `~/.dem2dsf/gui_prefs.json` (override with
`DEM2DSF_GUI_PREFS`).

The GUI supports optional AOI paths and tile inference for quick builds.

### Profiling and benchmarks

```bash
dem2dsf build --profile --metrics-json perf.json --dem dem.tif --tile +47+008
python scripts/profile_build.py --dem dem.tif --tile +47+008 --summary
python scripts/run_ci_perf.py --output-dir perf_ci --runs 1
```

## Development

```bash
python scripts/install_dev.py
ruff check .
pytest --cov=dem2dsf --cov-report=term-missing
pytest -m e2e
pytest -m integration
```

Package the GUI bundle with:

```bash
python scripts/build_gui.py
```

## Dependencies

- Python 3.13
- Core: rasterio (GDAL), pyproj, numpy, jsonschema
- Dev: pytest, pytest-cov, ruff, build
- Optional: fiona (AOI shapefile support)
- Optional: pyinstaller + pillow (GUI bundling)
- External: Ortho4XP 1.40+, DSFTool/DDSTool (XPTools), 7-Zip for DSF compression
- Optional data: X-Plane 12 Global Scenery for XP12 enrichment
