# Compatibility

## Supported platforms
- Windows, macOS, and Linux with Python 3.13+.
- x86_64 and arm64 are supported when the Python GIS stack (GDAL/rasterio) is available.

## External tools
- Ortho4XP: baseline 1.40 (XP12 water/raster behavior).
- XPTools (DSFTool/DDSTool): 24-5 binaries; DSFTool 2.2+ is required for 7z-compressed DSFs.
- 7-Zip: optional, only required for `--dsf-7z` packaging.

## Version policy
- Prefer the pinned baseline in `pinned_versions.md`.
- Newer tool versions are allowed but should be treated as unvalidated until verified.
- Build reports and publish manifests capture tool paths/versions when available; include them when sharing results.
