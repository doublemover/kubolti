"""Custom Scenery conflict scanning utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dem2dsf.xplane_paths import tile_from_dsf_path


def _read_scenery_packs(root: Path) -> list[str] | None:
    """Parse scenery_packs.ini to determine package order."""
    ini_path = root / "scenery_packs.ini"
    if not ini_path.exists():
        return None
    packs: list[str] = []
    for line in ini_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("SCENERY_PACK"):
            _, pack_path = stripped.split(maxsplit=1)
            packs.append(Path(pack_path).name)
    return packs


def _is_overlay_pack(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("yortho4xp_") or "overlay" in lowered


def _is_base_mesh_pack(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("zortho4xp_") or "mesh" in lowered


def suggested_scenery_order(packs: list[str]) -> list[str]:
    """Return a suggested scenery pack order for Ortho4XP content."""
    if not packs:
        return []
    overlays = [pack for pack in packs if _is_overlay_pack(pack)]
    meshes = [pack for pack in packs if _is_base_mesh_pack(pack)]
    others = [pack for pack in packs if pack not in overlays and pack not in meshes]
    return others + overlays + meshes


def scenery_order_snippet(packs: list[str]) -> list[str]:
    """Return a scenery_packs.ini snippet for a suggested order."""
    return [f"SCENERY_PACK {pack}" for pack in packs]


def validate_overlay_source(path: Path | None) -> dict[str, Any]:
    """Validate a Global Scenery overlay source path."""
    if not path:
        return {
            "status": "warn",
            "detail": "overlay source not configured",
            "path": None,
        }
    if not path.exists():
        return {
            "status": "error",
            "detail": f"overlay source not found: {path}",
            "path": str(path),
        }
    earth_dir = path / "Earth nav data"
    if not earth_dir.exists():
        return {
            "status": "error",
            "detail": f"overlay source missing Earth nav data: {path}",
            "path": str(path),
        }
    return {
        "status": "ok",
        "detail": "overlay source looks valid",
        "path": str(path),
    }


def scan_custom_scenery(root: Path, *, tiles: list[str] | None = None) -> dict[str, Any]:
    """Scan a Custom Scenery folder for tiles provided by multiple packs."""
    tile_to_packs: dict[str, list[str]] = {}
    if tiles:
        for tile in tiles:
            for dsf_path in root.rglob(f"Earth nav data/*/{tile}.dsf"):
                pack_root = dsf_path.parents[2]
                tile_to_packs.setdefault(tile, []).append(pack_root.name)
    else:
        for dsf_path in root.rglob("Earth nav data/*/*.dsf"):
            tile = tile_from_dsf_path(dsf_path)
            pack_root = dsf_path.parents[2]
            tile_to_packs.setdefault(tile, []).append(pack_root.name)

    for tile, packs in tile_to_packs.items():
        tile_to_packs[tile] = sorted(set(packs))

    scenery_packs = _read_scenery_packs(root)
    suggested_order = suggested_scenery_order(scenery_packs) if scenery_packs else None
    suggested_snippet = scenery_order_snippet(suggested_order) if suggested_order else None
    conflicts: list[dict[str, Any]] = []
    for tile, packs in sorted(tile_to_packs.items()):
        if len(packs) < 2:
            continue
        ordered = None
        if scenery_packs:
            ordered = [pack for pack in scenery_packs if pack in packs]
        conflicts.append(
            {
                "tile": tile,
                "packages": packs,
                "ordered_packages": ordered or packs,
                "recommendation": (
                    "Keep only one base mesh per tile and ensure the desired pack "
                    "is lower in scenery_packs.ini."
                ),
            }
        )

    return {
        "scenery_root": str(root),
        "tiles": tile_to_packs,
        "conflicts": conflicts,
        "scenery_packs": scenery_packs,
        "suggested_order": suggested_order,
        "suggested_order_snippet": suggested_snippet,
    }
