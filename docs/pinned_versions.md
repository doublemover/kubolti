# Pinned Versions

This project targets Python 3.13 and the toolchain versions below. Update this list as integrations are validated.

- Python: 3.13
- Ortho4XP: 1.40 (XP12 water/raster behavior)
- XPTools (DSFTool/DDSTool): XPTools_2020
- GDAL: 3.11+ (unified CLI and modern raster tooling)
- XPTools source tag: XPTools_2020 (commit fe5714ec839f0db1e084f09d4c06f536dd9e3086)
- Windows build toolchain: Visual Studio 2017+ (toolset v141, MSBuild)

Notes:
- DSFTool/DDSTool are built from the same pinned XPTools tag.
- External tools are BYO binaries; the install script only handles Python dependencies.
- Version changes should be reflected in build reports for reproducibility.
