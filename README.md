# DEM2DSF (kubolti)

![CI](https://github.com/doublemover/kubolti/actions/workflows/ci.yml/badge.svg)
![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

<p align="center">
  <img width="256" height="256" alt="logo" src="https://github.com/user-attachments/assets/d13fa407-6cea-44dc-902f-e4ef51ee69a8" />
</p>

DEM2DSF is a CLI-first pipeline that turns GeoTIFF DEMs into X-Plane 12 base-mesh
DSF tiles. It handles the GIS glue (mosaic, reproject, tile, fill) and then
orchestrates Ortho4XP + XPTools to produce reproducible artifacts and validation
reports.

Feature requests are encouraged and welcome. If you want something, open an
issue with: (1) the goal, (2) sample inputs or constraints, (3) expected outputs,
and (4) any gotchas you already know.

## Quickstart

```bash
python -m venv .venv
python -m pip install -e .
dem2dsf --help
```

## Current capabilities

- DEM normalization: mosaic sources, warp to EPSG:4326, tile, fill.
- Ortho4XP runner orchestration with per-tile DEM staging and density presets.  
- DSFTool round-trip checks + XP12 raster inventory (enrichment in progress).   
- Normalization cache reuse keyed by inputs/params.
- Wizard flow, overlay generators, presets (including ultra density), publish zip artifacts.
- DSF compression with 7-Zip (optional backup of the uncompressed DSF).
- Ortho4XP tile cfg preservation for provenance.
- Coverage thresholds + metrics, diagnostics bundles, and per-tile runner logs.
- Runner timeouts, retries, log streaming, and opt-in config persistence.
- Mosaic strategy selection (full mosaic or per-tile merge).
- Tkinter GUI launcher with persisted preferences.

## Roadmap highlights

See `COMPLETE_PLAN.md` for the full sequence. Highlights:
- Tighten Ortho4XP presets and autoortho ergonomics.
- Improve XPTools integration + DSF validation coverage.
- Expand integration/e2e coverage and performance profiling.

## External tools and discovery

DEM2DSF orchestrates external tools (BYO):
- Ortho4XP: https://github.com/oscarpilote/Ortho4XP (target baseline 1.40)
- XPTools: https://developer.x-plane.com/tools/xptools/ (DSFTool, DDSTool)
  - DSFTool 2.2+ is required to read 7z-compressed DSFs directly.

It auto-loads `tools/tool_paths.json` when present (or set `DEM2DSF_TOOL_PATHS`).
To install/discover common tools and write config:

```bash
python scripts/install_tools.py --write-config
```

Source builds (DSFTool/DDSTool) are preferred; pass `--allow-downloads` to
permit zip downloads if builds fail. The build script checks out XPTools_2024_5
by default; use `--xptools-commit` to pin a specific SHA.

```bash
python scripts/build_xptools.py --install-deps --write-config
```

If `tools/xptools` already contains the binaries (or they are on PATH), the
script reuses them instead of rebuilding. On Windows, source builds use the
MSVC solution (`msvc/XPTools.sln`). Set `DEM2DSF_MSBUILD_PATH` and/or
`DEM2DSF_VCVARSALL_PATH` if detection fails.

## Usage guide (by purpose)

Tip: after install you can run either `dem2dsf ...` or `python -m dem2dsf ...`.

### Build tiles

```bash
dem2dsf build --dem dem.tif --tile +47+008 --output build
```

Use `--tile-jobs 4` to parallelize per-tile normalization work.

If Ortho4XP is not auto-detected, pass a runner command:
`--runner python scripts/ortho4xp_runner.py --ortho-root <dir>`.

### Runner reliability

```bash
dem2dsf build --dem dem.tif --tile +47+008 --output build \
  --runner-timeout 3600 --runner-retries 1 --runner-stream-logs
```

Runner flags can include `--persist-config` when using the bundled runner if
you want Ortho4XP.cfg changes to stay applied after the run.

### Logging

Add `--verbose` or `--quiet` for CLI log verbosity. Use `--log-file path.json`  
to write structured JSON logs or `--log-json` to emit JSON logs on stderr.      

The Ortho4XP runner writes per-tile JSON logs to
`<output>/runner_logs/ortho4xp_<tile>.run.log` unless `--log-file` overrides it.

### Coverage and diagnostics

```bash
dem2dsf build --dem dem.tif --tile +47+008 --output build \
  --coverage-min 0.95 --coverage-hard-fail --coverage-metrics \
  --bundle-diagnostics
```

Coverage thresholds apply to DEM coverage within each tile. Diagnostics bundles
create `diagnostics_<timestamp>.zip` in the build directory with reports, logs,
metrics, and profiles when available.

### DEM stacks (multi-resolution)

```bash
dem2dsf build --dem-stack stack.json --tile +47+008 --output build
```

### Wizard (guided)

```bash
dem2dsf wizard --dem dem.tif --tile +47+008 --output build --defaults
```

### Validate / diagnose

```bash
dem2dsf doctor --runner <cmd...> --dsftool <path>
dem2dsf scan --scenery-root "X-Plane 12/Custom Scenery"
```

### Publish artifacts

```bash
dem2dsf publish --build-dir build --output build.zip
```

With compressed DSFs: `--dsf-7z --sevenzip-path <path-to-7z>`.
Add `--dsf-7z-backup` to keep `.dsf.uncompressed` backups.

### Patch an existing build

```bash
dem2dsf patch --build-dir build --patch patch_plan.json --output patched
```

### Overlays

```bash
dem2dsf overlay --build-dir build --output overlay
```

Use `dem2dsf overlay --help` for generator-specific options.

### Ortho4XP cache cleanup

```bash
dem2dsf cache list --ortho-root "C:/Ortho4XP" --tile +47+008
dem2dsf cache purge --ortho-root "C:/Ortho4XP" --tile +47+008 --confirm
```

### Presets

```bash
dem2dsf presets list
dem2dsf presets show usgs-13as
dem2dsf presets export --output my_presets.json
dem2dsf presets import my_presets.json
```

### GUI

```bash
dem2dsf gui
```

Preferences are saved to `~/.dem2dsf/gui_prefs.json` (override with
`DEM2DSF_GUI_PREFS`).

### Profiling and benchmarks

```bash
dem2dsf build --profile --metrics-json perf.json --dem dem.tif --tile +47+008
python scripts/profile_build.py --dem dem.tif --tile +47+008 --summary
python scripts/run_ci_perf.py --output-dir perf_ci --runs 1
```

## Development

- Lint: `ruff check .`
- Tests + coverage: `pytest --cov=dem2dsf --cov-report=term-missing`
- E2E tests: `pytest -m e2e`
- Integration tests (external tools + Global Scenery if available):
  `pytest -m integration`
- Package GUI (PyInstaller): `python scripts/build_gui.py`

## Dependencies

- Python 3.13
- rasterio (GDAL), pyproj, numpy, jsonschema
- pytest, pytest-cov, ruff (dev)
- Optional: pyinstaller + pillow (GUI bundling / PNG icons)
- External tools (BYO): Ortho4XP 1.40+, DSFTool/DDSTool (XPTools)
- Optional: 7-Zip for DSF compression; X-Plane Global Scenery for XP12
  enrichment
