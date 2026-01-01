# Reference Index

This directory collects short summaries of external references cited in the spec. Forum entries were summarized from local MHTML captures.
Fetcher: `python scripts/fetch_references.py --out-dir <path>` writes raw captures for review.

## X-Plane DSF and Tools
- docs/references/xplane_dsf_usage.md - DSF properties, raster layers, 7z compression.
- docs/references/xplane_dsf_base_meshes.md - layers, patches, physical mesh.
- docs/references/xplane_xptools.md - DSFTool and related tools.
- docs/references/xplane_tools_index.md - index of other official X-Plane tools.
- docs/references/file_formats.md - local format and artifact definitions.
- docs/references/gotchas.md - common pitfalls and failure modes.
- docs/references/performance_tuning.md - tuning and performance notes.

## Ortho4XP and Community Guidance
- docs/references/ortho4xp_repo.md - repo notes and XP12 compatibility.
- docs/references/ortho4xp_forum_dem_config.md - DEM config constraints and custom DEM requirements.
- docs/references/ortho4xp_forum_own_orthos.md - Workflow for supplying local orthos.
- docs/references/ortho4xp_forum_dem_mosaic.md - Mosaic pitfalls and blending advice.
- docs/references/ortho4xp_forum_epsg4326.md - EPSG:4326 vs EPSG:3857 expectations.
- docs/references/ortho4xp_reddit_5m_mesh.md - 5m mesh size, triangle count, and input checks.

## AutoOrtho
- docs/references/autoortho_details.md - virtual file system approach, naming, skip_downloads.
- docs/references/autoortho_repo.md - repo context.

## GDAL and CRS
- docs/references/gdalwarp.md - reprojection options and nodata handling.
- docs/references/gdal_osr_axis_order.md - axis order behavior and SetAxisMappingStrategy.
- docs/references/gdal_programs_cli.md - current CLI index and unified gdal entry point.
- docs/references/gdal_translate.md - format conversion, subsetting, and resampling options.
- docs/references/gdalbuildvrt.md - VRT mosaics and resolution control.
- docs/references/gdal_retile.md - official tiling and pyramid utility.

## GIS Utilities and Data Sources
- docs/references/gis_stackexchange_gdal_retile.md - gdal_retile and gdal_translate tiling patterns.
- docs/references/gis_stackexchange_pyproj_webmercator.md - EPSG:3857 question; answer not captured.
- docs/references/alpilotx_uhd_mesh_sources.md - UHD mesh elevation data sources and OSM vintages.
- docs/references/mapplus_dhm_portal.md - GeoGR portal moved; new link needed.
- docs/references/ortho4xp_imagery_utils_source.md - GitHub load error; use raw or local clone.
