# GUI Launcher

The GUI wraps common build and publish flows for non-CLI users. It supports
presets, file pickers, and tool auto-detection.

## Launch
```bash
python -m dem2dsf gui
```

## Build tab highlights
- Presets can populate backend defaults (quality, density, resampling).
- DEMs can be selected via the file picker or via a DEM stack JSON.
- Ortho4XP/DSFTool fields are optional if `tools/tool_paths.json` is
  present (or `DEM2DSF_TOOL_PATHS` is set).
- Ortho4XP python points at the interpreter used by Ortho4XP (optional).
- Ortho4XP batch mode toggles `--batch` on the runner for headless runs.
- Runner override accepts a custom command when you need a non-default launcher.
- Runner timeout/retry/stream toggles control reliability and log streaming.
- Persist Ortho4XP.cfg keeps config overrides after the run (default restores).
- Override destination nodata and triangle guardrails when tuning raster output.
- Mosaic strategy and coverage thresholds tune normalization behavior.
- Diagnostics bundles capture reports/logs/metrics into a zip.
- XP12 enrichment, dry runs, and build profiling can be toggled.

## Preferences
The GUI stores the most recent values in `~/.dem2dsf/gui_prefs.json`. Override
the location with `DEM2DSF_GUI_PREFS`.

## Publish tab highlights
- Browse buttons fill build/output paths.
- Optional 7z compression can be enabled with a detected or selected 7z path.
  Use the backup toggle to keep `.dsf.uncompressed` files after compression.

## Standalone packaging
Use PyInstaller to generate a standalone GUI bundle:
```bash
python -m pip install pyinstaller
python scripts/build_gui.py
```

Options:
- `--onedir` to build a directory bundle instead of a single file.
- `--console` to keep a console window visible.
- `--icon <path>` to set a custom icon.
- On Windows, PNG icons require Pillow; otherwise provide an `.ico` or use `--no-icon`.
