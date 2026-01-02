# DEM Stack Guide

DEM stacks let you layer multiple DEM sources by priority and optional AOI masks.
The pipeline blends higher-priority layers on top of lower-priority layers per tile.

## JSON format

```json
{
  "layers": [
    {
      "path": "data/high_res.tif",
      "priority": 10,
      "aoi": "data/high_res_aoi.json",
      "nodata": -9999
    },
    {
      "path": "data/low_res.tif",
      "priority": 0
    }
  ]
}
```

## Notes
- `priority` sorts low to high; higher layers win where they have data.
- `aoi` expects a GeoJSON Polygon or FeatureCollection.
- AOI defaults to EPSG:4326 when CRS metadata is missing; embed CRS metadata if different.
- If `aoi` is set, ensure a nodata value is provided (via `nodata` or `--dst-nodata`).
- Use `--dem-stack <path>` with `dem2dsf build`, `wizard`, or `autoortho`.
