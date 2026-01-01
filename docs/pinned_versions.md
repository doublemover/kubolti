# Pinned Versions

This project targets Python 3.13 and the toolchain versions below. Update this list as integrations are validated.

- Python: 3.13
- Ortho4XP: 1.40 (XP12 water/raster behavior)
- XPTools (DSFTool/DDSTool): 24-5 binaries (tools page zip)
- GDAL: 3.11+ (unified CLI and modern raster tooling)

Notes:
- External tools are BYO binaries; `scripts/install_tools.py` can fetch XPTools zips.
- Version changes should be reflected in build reports for reproducibility.
- The build pipeline reads pinned versions from `src/dem2dsf/resources/pinned_versions.json`.
- Override the pinned config with `DEM2DSF_PINNED_VERSIONS` or `--pinned-versions`.
- Build reports surface pinned-version drift in the provenance block; strict mode also emits warnings.
