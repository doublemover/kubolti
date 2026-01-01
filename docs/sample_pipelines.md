# Sample Pipelines

These pipelines are intentionally lightweight and map to common region types.
Swap in your own DEM sources and tile lists as needed.

## North America (USGS 1/3 arc-second, Ortho4XP)
```bash
python -m dem2dsf build \
  --dem data/usgs_13as.tif \
  --tile +47+008 \
  --tile +48+008 \
  --output build_usgs \
  --resampling bilinear \
  --density high
```

## Europe (EU-DEM in ETRS89 / UTM, reprojection + fill)
```bash
python -m dem2dsf build \
  --dem data/eu_dem_utm32.tif \
  --tile +47+008 \
  --output build_eudem \
  --target-crs EPSG:4326 \
  --resampling cubic \
  --fill-strategy interpolate
```

## Global (SRTM + fallback void fill)
```bash
python -m dem2dsf build \
  --dem data/srtm_global.tif \
  --fallback-dem data/alos_world.tif \
  --tile +35-120 \
  --output build_global \
  --fill-strategy fallback
```

## High-res patch stack (local LiDAR over global DEM)
Create a stack JSON like:
```json
{
  "layers": [
    {"path": "data/lidar_local.tif", "priority": 10},
    {"path": "data/global_dem.tif", "priority": 1}
  ]
}
```
Then run:
```bash
python -m dem2dsf build \
  --dem-stack stack.json \
  --tile +47+008 \
  --output build_stack
```

## Optional overlay packaging
```bash
python -m dem2dsf overlay \
  --generator copy \
  --build-dir build_usgs \
  --output overlay_usgs \
  --tile +47+008
```
