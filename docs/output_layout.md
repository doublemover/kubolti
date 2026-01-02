# Output layout

DEM2DSF writes build artifacts under the output directory (default: `build/`).
The layout is intentionally simple so you can version, diff, or clean it with
shell scripts.

## Top-level files

- `build_plan.json`: inputs, options, and intended tiles for the run.
- `build_report.json`: per-tile status plus warnings/errors.
- `build_config.lock.json`: locked snapshot of inputs/options/tools for replay.
- `diagnostics_YYYYMMDD_HHMMSS.zip`: optional bundle created by
  `--bundle-diagnostics`.
- `metrics.json` / `*.metrics.json`: optional performance summaries.

## Directories

- `Earth nav data/<bucket>/<tile>.dsf`: DSF outputs from Ortho4XP.
- `terrain/`, `textures/`: scenery assets copied from Ortho4XP outputs.
- `normalized/`: cached mosaics and per-tile normalized DEMs.
- `runner_logs/`: Ortho4XP runner logs (`.run.log`, `.stdout.log`,
  `.stderr.log`, `.events.json`, `.config.json`).
- `dsf_validation/`: DSFTool roundtrip outputs and validation text files.
- `xp12/`: XP12 raster inventory/enrichment outputs.

## Cleanup

Use `dem2dsf clean --build-dir build` for a dry-run summary. Add `--confirm`
to delete and `--include` to target specific groups, for example:

```bash
dem2dsf clean --build-dir build --include normalized --include runner-logs --confirm
```
