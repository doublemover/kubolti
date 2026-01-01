# Sources (primary links consulted)

## Ortho4XP pipeline & user workflow
- Mudspike Ortho4XP guide (steps 1/2/2.5/3, artifact notes): https://forums.mudspike.com/t/x-plane-ortho4xp-guide/3416
- X‑Plane.org “Help with order please” (overlay source path + scenery_packs order example): https://forums.x-plane.org/forums/topic/162353-help-with-order-please/

## Folder layout & artifact structure
- X‑Plane.org “Combining numerous ortho files” (shows `Earth nav data`, `terrain`, `textures`, `.mesh` structure): https://forums.x-plane.org/forums/topic/199694-combining-numerous-ortho-files/
- X‑Plane.org “Python: Symlink all ortho files to one scenery folder” (notes `zOrtho4XP_` folder expectations, linking strategy): https://forums.x-plane.org/forums/topic/309971-python-symlink-all-ortho-files-to-one-scenery-folder/

## DEM file naming & placement
- X‑Plane.org “sort Ortho4XP elevation data files” (10°x10° bucket folders; naming conventions): https://forums.x-plane.org/forums/topic/239911-how-do-i-sort-ortho4xp-elevation-data-files-to-the-correct-folder/
- X‑Plane.org “elevation data & config” (custom DEM requirements; default DEM source discussion): https://forums.x-plane.org/forums/topic/156476-question-regarding-elevation-data-and-ortho4xp-config-file/

## Config knobs & multi-DEM refinement
- Oscar Pilote posts (multi-DEM refine via `iterate`, and example mesh settings): https://forums.x-plane.org/profile/461408-oscar-pilote/content/?page=5&type=forums_topic_post
- X‑Plane.org “Ortho4XP and XP12, curvature_tol” (triangle count impact example): https://forums.x-plane.org/forums/topic/301742-ortho4xp-and-xp12-curvature_tol/?comment=2674263&do=findComment
- Ortho4XP GitHub issue showing full build log + config dump (includes many params): https://github.com/oscarpilote/Ortho4XP/issues/226

## Common failures / troubleshooting
- X‑Plane.org “unable to build mesh… tiny triangles / min angle” (Triangle4XP failure message): https://forums.x-plane.org/forums/topic/185097-ortho4xp-issue-unable-to-build-mesh-for-scenery/?comment=1705735&do=findComment
- SLW68 content page (community advice on Triangle4XP min_angle ranges, bathymetry overlay source nuance): https://forums.x-plane.org/index.php?/profile/685990-slw68/content/?&page=8
- Ortho4XP GitHub issue on installation constraints (Python 3.10 / numpy<2 guidance): https://github.com/oscarpilote/Ortho4XP/issues/276
- X‑Plane.org “XP12 Ortho4XP file sizes” (tile root cfg as provenance): https://forums.x-plane.org/forums/topic/300177-xp12-ortho4xp-file-sizes/

## Scenery ordering behavior (official)
- X‑Plane Support: “Controlling Custom Scenery Pack Order…” (priority rules; base meshes to bottom): https://x-plane.helpscoutdocs.com/article/61-controlling-custom-scenery-pack-order-in-x-plane-11

## Ortho4XP upstream project context
- Ortho4XP GitHub repo (README notes transition to v1.40 for XP12 water requirements, plus seasons/sounds rasters): https://github.com/oscarpilote/Ortho4XP
