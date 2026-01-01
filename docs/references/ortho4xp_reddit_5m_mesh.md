# Ortho4XP 5m Mesh Reddit Post

Source: https://www.reddit.com/r/flightsim/comments/96t02m/managed_to_get_a_5m_mesh_working_with_ortho_in/

## Why it matters
Shows real-world size, triangle count, and workflow checks for a high-resolution Ortho4XP mesh.

## Key points
- Reported output: about a 20 GB tile from a 1.5 GB DEM at ZL17 (ZL19 near airports), around 6 million triangles; FPS dip but still above 30 without dynamic LOD.
- Troubleshooting advice: use Ortho4XP 1.30 dev and verify DEM inputs with gdalinfo (exact 1x1 extent, square grid, NA value).
- Sea masks and shoreline textures can conflict with orthos; cleanup and tuning are still needed.
- For 1m LIDAR, very low curv_tol may be required, which can produce extremely large meshes.

## Gotchas
- High-resolution DEMs can create very large meshes; triangle budgets and curv_tol tuning matter.
- Shoreline artifacts and water behavior are recurring pain points at high detail.
