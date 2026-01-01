# Preset Library

Presets capture common dataset defaults and example CLI usage. They are meant
as a starting point, not a replacement for project-specific tuning.

## User presets
User-defined presets are loaded from `~/.dem2dsf/presets.json` by default.
Set `DEM2DSF_PRESETS_PATH` to point at a different JSON file. User presets
override built-ins with the same name.

## Available presets
- `usgs-13as`: USGS 1/3 arc-second, denser mesh, EPSG:4326.
- `eu-dem-utm`: EU-DEM in ETRS89/UTM with reprojection and interpolation.
- `srtm-fallback`: SRTM with fallback DEMs for void fill.
- `lidar-stack`: LiDAR + global DEM using a stack JSON.

## CLI usage
List presets:
```bash
python -m dem2dsf presets list
```

Show a preset in text:
```bash
python -m dem2dsf presets show usgs-13as
```

Show a preset in JSON:
```bash
python -m dem2dsf presets show usgs-13as --format json
```

Export user presets to JSON:
```bash
python -m dem2dsf presets export --output my_presets.json
```

Export user presets + built-ins:
```bash
python -m dem2dsf presets export --include-builtins --output all_presets.json
```

Import presets into the user file:
```bash
python -m dem2dsf presets import my_presets.json
```

## JSON format
```json
{
  "version": 1,
  "presets": [
    {
      "name": "custom",
      "summary": "My custom preset.",
      "inputs": ["Source DEM"],
      "options": {"density": "low"},
      "notes": ["Optional tuning note"],
      "example": "python -m dem2dsf build --density low"
    }
  ]
}
```
