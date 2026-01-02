"""Overlay generation helpers and plugin registry."""

from __future__ import annotations

import importlib.util
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path
from dem2dsf.xplane_paths import tile_from_dsf_path


@dataclass(frozen=True)
class OverlayRequest:
    """Input for overlay generators."""

    build_dir: Path | None
    output_dir: Path
    tiles: tuple[str, ...]
    options: dict[str, Any]


@dataclass(frozen=True)
class OverlayResult:
    """Result from an overlay generator."""

    generator: str
    artifacts: dict[str, Any]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


class OverlayGenerator(Protocol):
    """Protocol for overlay generator plugins."""

    name: str

    def generate(self, request: OverlayRequest) -> OverlayResult:
        """Generate overlay artifacts for a build request."""
        raise NotImplementedError


class OverlayRegistry:
    """Registry for overlay generators."""

    def __init__(self) -> None:
        """Initialize an empty overlay generator registry."""
        self._generators: dict[str, OverlayGenerator] = {}

    def register(self, generator: OverlayGenerator) -> None:
        """Register a new overlay generator by name."""
        if generator.name in self._generators:
            raise ValueError(f"Overlay generator already registered: {generator.name}")
        self._generators[generator.name] = generator

    def get(self, name: str) -> OverlayGenerator | None:
        """Return a registered generator by name."""
        return self._generators.get(name)

    def names(self) -> tuple[str, ...]:
        """Return registered generator names."""
        return tuple(sorted(self._generators))


def _update_terrain_text(text: str, texture_ref: str) -> tuple[str, int]:
    """Rewrite texture references in terrain text and count updates."""
    lines = []
    updated = 0
    for raw_line in text.splitlines():
        line = raw_line
        if ".dds" in raw_line.lower() or ".png" in raw_line.lower():
            parts = raw_line.split()
            if parts and parts[0] in {"TEXTURE", "BASE_TEX", "TEXTURE_LIT"}:
                line = f"{parts[0]} {texture_ref}"
                updated += 1
        lines.append(line)
    return "\n".join(lines) + "\n", updated


def apply_drape_texture(
    build_dir: Path,
    output_dir: Path,
    texture_path: Path,
    *,
    terrain_glob: str = "*.ter",
    texture_name: str | None = None,
) -> dict[str, Any]:
    """Copy a build and rewrite terrain files to use a drape texture."""
    if not build_dir.exists():
        raise FileNotFoundError(f"Build directory not found: {build_dir}")
    terrain_dir = build_dir / "terrain"
    if not terrain_dir.exists():
        raise FileNotFoundError(f"Terrain directory not found: {terrain_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ("Earth nav data", "terrain"):
        src = build_dir / subdir
        if src.exists():
            shutil.copytree(src, output_dir / subdir, dirs_exist_ok=True)

    textures_dir = output_dir / "textures"
    textures_dir.mkdir(parents=True, exist_ok=True)
    texture_name = texture_name or texture_path.name
    texture_dest = textures_dir / texture_name
    shutil.copy(texture_path, texture_dest)

    updated_files = 0
    updated_lines = 0
    texture_ref = f"../textures/{texture_name}"
    for terrain_path in (output_dir / "terrain").rglob(terrain_glob):
        text = terrain_path.read_text(encoding="utf-8")
        updated_text, updates = _update_terrain_text(text, texture_ref)
        if updates:
            terrain_path.write_text(updated_text, encoding="utf-8")
            updated_files += 1
            updated_lines += updates

    return {
        "texture": str(texture_dest),
        "terrain_updated": updated_files,
        "texture_ref": texture_ref,
        "lines_updated": updated_lines,
    }


def _count_files(root: Path, pattern: str = "*") -> int:
    """Count files under a root path matching a glob pattern."""
    return sum(1 for path in root.rglob(pattern) if path.is_file())


def copy_overlay_assets(
    *,
    build_dir: Path,
    output_dir: Path,
    tiles: tuple[str, ...],
    include_terrain: bool,
    include_textures: bool,
) -> dict[str, Any]:
    """Copy overlay-ready assets from a build directory into a new output."""
    if not build_dir.exists():
        raise FileNotFoundError(f"Build directory not found: {build_dir}")
    earth_dir = build_dir / "Earth nav data"
    if not earth_dir.exists():
        raise FileNotFoundError(f"Earth nav data not found: {earth_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_earth = output_dir / "Earth nav data"
    output_earth.mkdir(parents=True, exist_ok=True)

    missing_tiles: list[str] = []
    copied_tiles: list[str] = []
    if tiles:
        for tile in tiles:
            src_dsf = xplane_dsf_path(build_dir, tile)
            if not src_dsf.exists():
                missing_tiles.append(tile)
                continue
            dest_dsf = xplane_dsf_path(output_dir, tile)
            dest_dsf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_dsf, dest_dsf)
            copied_tiles.append(tile)
    else:
        shutil.copytree(earth_dir, output_earth, dirs_exist_ok=True)
        copied_tiles = sorted({tile_from_dsf_path(path) for path in output_earth.rglob("*.dsf")})

    dsf_files = _count_files(output_earth, "*.dsf")
    terrain_files = 0
    texture_files = 0
    if include_terrain:
        terrain_src = build_dir / "terrain"
        if terrain_src.exists():
            shutil.copytree(terrain_src, output_dir / "terrain", dirs_exist_ok=True)
            terrain_files = _count_files(output_dir / "terrain")
    if include_textures:
        textures_src = build_dir / "textures"
        if textures_src.exists():
            shutil.copytree(textures_src, output_dir / "textures", dirs_exist_ok=True)
            texture_files = _count_files(output_dir / "textures")

    return {
        "tiles_copied": copied_tiles,
        "missing_tiles": missing_tiles,
        "dsf_files": dsf_files,
        "terrain_files": terrain_files,
        "texture_files": texture_files,
    }


def _extract_texture_refs(text: str) -> set[str]:
    """Extract texture references from terrain definitions."""
    refs = set()
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] in {"TEXTURE", "BASE_TEX", "TEXTURE_LIT", "BORDER_TEX"}:
            if len(parts) > 1:
                refs.add(parts[1])
    return refs


def inventory_overlay_assets(
    *,
    build_dir: Path,
    output_dir: Path,
    tiles: tuple[str, ...],
) -> dict[str, Any]:
    """Scan an existing build for overlay assets and write an inventory."""
    if not build_dir.exists():
        raise FileNotFoundError(f"Build directory not found: {build_dir}")
    earth_dir = build_dir / "Earth nav data"
    if not earth_dir.exists():
        raise FileNotFoundError(f"Earth nav data not found: {earth_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    dsf_paths: list[str] = []
    tile_names: set[str] = set()
    if tiles:
        for tile in tiles:
            candidate = xplane_dsf_path(build_dir, tile)
            if candidate.exists():
                dsf_paths.append(str(candidate))
                tile_names.add(tile)
    else:
        for candidate in earth_dir.rglob("*.dsf"):
            dsf_paths.append(str(candidate))
            tile_names.add(tile_from_dsf_path(candidate))

    terrain_dir = build_dir / "terrain"
    terrain_files: list[str] = []
    texture_refs: set[str] = set()
    if terrain_dir.exists():
        for terrain_path in terrain_dir.rglob("*.ter"):
            terrain_files.append(str(terrain_path))
            text = terrain_path.read_text(encoding="utf-8")
            texture_refs.update(_extract_texture_refs(text))

    inventory = {
        "tiles": sorted(tile_names),
        "dsf_paths": sorted(dsf_paths),
        "terrain_files": sorted(terrain_files),
        "texture_refs": sorted(texture_refs),
    }
    inventory_path = output_dir / "overlay_inventory.json"
    inventory_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return {
        "inventory_path": str(inventory_path),
        "tile_count": len(tile_names),
        "dsf_count": len(dsf_paths),
        "terrain_count": len(terrain_files),
        "texture_ref_count": len(texture_refs),
    }


class DrapeOverlayGenerator:
    """Generator that rewrites terrain textures for drape overlays."""

    name = "drape"

    def generate(self, request: OverlayRequest) -> OverlayResult:
        """Generate a drape overlay based on a build directory."""
        texture = request.options.get("texture")
        if not texture:
            return OverlayResult(
                generator=self.name,
                artifacts={},
                warnings=(),
                errors=("drape requires a texture path",),
            )
        build_dir = request.build_dir
        if not build_dir:
            return OverlayResult(
                generator=self.name,
                artifacts={},
                warnings=(),
                errors=("drape requires --build-dir",),
            )
        artifacts = apply_drape_texture(
            build_dir,
            request.output_dir,
            Path(texture),
            terrain_glob=request.options.get("terrain_glob", "*.ter"),
            texture_name=request.options.get("texture_name"),
        )
        return OverlayResult(
            generator=self.name,
            artifacts=artifacts,
            warnings=(),
            errors=(),
        )


class CopyOverlayGenerator:
    """Generator that copies existing overlay assets into a new package."""

    name = "copy"

    def generate(self, request: OverlayRequest) -> OverlayResult:
        """Copy overlay assets out of a build directory."""
        build_dir = request.build_dir
        if not build_dir:
            return OverlayResult(
                generator=self.name,
                artifacts={},
                warnings=(),
                errors=("copy requires --build-dir",),
            )
        include_terrain = bool(request.options.get("include_terrain", True))
        include_textures = bool(request.options.get("include_textures", True))
        warnings: list[str] = []
        try:
            artifacts = copy_overlay_assets(
                build_dir=build_dir,
                output_dir=request.output_dir,
                tiles=request.tiles,
                include_terrain=include_terrain,
                include_textures=include_textures,
            )
        except FileNotFoundError as exc:
            return OverlayResult(
                generator=self.name,
                artifacts={},
                warnings=(),
                errors=(str(exc),),
            )
        if artifacts["missing_tiles"]:
            warnings.append(f"Missing tiles: {', '.join(artifacts['missing_tiles'])}")
        if include_terrain and artifacts["terrain_files"] == 0:
            warnings.append("No terrain files copied.")
        if include_textures and artifacts["texture_files"] == 0:
            warnings.append("No texture files copied.")
        return OverlayResult(
            generator=self.name,
            artifacts=artifacts,
            warnings=tuple(warnings),
            errors=(),
        )


class InventoryOverlayGenerator:
    """Generator that inventories overlay assets without copying them."""

    name = "inventory"

    def generate(self, request: OverlayRequest) -> OverlayResult:
        """Scan an existing build and emit an overlay inventory report."""
        build_dir = request.build_dir
        if not build_dir:
            return OverlayResult(
                generator=self.name,
                artifacts={},
                warnings=(),
                errors=("inventory requires --build-dir",),
            )
        try:
            artifacts = inventory_overlay_assets(
                build_dir=build_dir,
                output_dir=request.output_dir,
                tiles=request.tiles,
            )
        except FileNotFoundError as exc:
            return OverlayResult(
                generator=self.name,
                artifacts={},
                warnings=(),
                errors=(str(exc),),
            )
        return OverlayResult(
            generator=self.name,
            artifacts=artifacts,
            warnings=(),
            errors=(),
        )


def load_overlay_plugin(path: Path, registry: OverlayRegistry) -> None:
    """Load a plugin module and register its generators."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if not spec or not spec.loader:
        raise ValueError(f"Unable to load plugin: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "register"):
        module.register(registry)
    plugin = getattr(module, "PLUGIN", None)
    if plugin is not None:
        registry.register(plugin)


def run_overlay(
    *,
    build_dir: Path | None,
    output_dir: Path,
    generator: str,
    tiles: tuple[str, ...],
    options: dict[str, Any],
    plugin_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Run an overlay generator and write an overlay report."""
    registry = OverlayRegistry()
    registry.register(DrapeOverlayGenerator())
    registry.register(CopyOverlayGenerator())
    registry.register(InventoryOverlayGenerator())
    for plugin_path in plugin_paths or []:
        load_overlay_plugin(plugin_path, registry)

    selected = registry.get(generator)
    if not selected:
        raise ValueError(f"Unknown overlay generator: {generator}")

    request = OverlayRequest(
        build_dir=build_dir,
        output_dir=output_dir,
        tiles=tiles,
        options=options,
    )
    result = selected.generate(request)
    report = {
        "generator": result.generator,
        "artifacts": result.artifacts,
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "tiles": list(tiles),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "overlay_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
