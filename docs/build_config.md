# Build config files

`dem2dsf build --config` accepts a JSON file with `inputs`, `options`, and
`tools` sections. CLI flags override config values.

## Example

```json
{
  "output_dir": "build",
  "inputs": {
    "dems": ["data/dem.tif"],
    "tiles": ["+47+008"],
    "aoi": "data/area.geojson",
    "aoi_crs": "EPSG:4326"
  },
  "options": {
    "quality": "compat",
    "density": "medium",
    "target_resolution": 30,
    "dsf_validation": "roundtrip",
    "resume": "build"
  },
  "tools": {
    "runner": ["python", "-m", "dem2dsf.runners.ortho4xp"],
    "dsftool": ["/path/to/DSFTool"],
    "ddstool": ["/path/to/DDSTool"]
  }
}
```

## Notes

- `inputs.dems` is a list of DEM paths. Use `inputs.dem_stack` for DEM stacks.
- `tools` commands are stored as command arrays (or a single string for the
  simple case).
- A locked snapshot of the merged config is written to
  `build_config.lock.json` in the output directory.
