# Patch Workflow

Patch plans let you rebuild only the affected tiles without re-running a full build.

## Patch plan JSON

```json
{
  "schema_version": "1",
  "patches": [
    {
      "tile": "+47+008",
      "dem": "patches/airport_fix.tif",
      "aoi": "patches/airport_aoi.json",
      "nodata": -9999
    }
  ]
}
```

## Apply a patch

```bash
python -m dem2dsf patch --build-dir build --patch patches/plan.json
```

By default, patched output lands in `build/patches/<plan-stem>/` and includes:
- `normalized/tiles/<tile>/<tile>.tif` with the patch applied.
- `patch_report.json` describing the patch run.
- `build_plan.json` and `build_report.json` from the patched build.

## Notes
- Patch DEMs are reprojected to match the base tile CRS/resolution.
- AOI masks require a nodata value to carve out the patch area.
- Supply `--output` to write patched tiles elsewhere.
