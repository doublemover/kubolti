"""Helpers for interacting with Ortho4XP scripts and outputs."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Iterable, Mapping

from dem2dsf.xplane_paths import (
    bucket_for_tile,
    elevation_data_path,
    hgt_tile_name,
    parse_tile,
)


class Ortho4XPNotFoundError(RuntimeError):
    """Raised when an Ortho4XP script cannot be located."""

    pass


TARGET_ORTHO4XP_VERSION = "1.40"
PYTHON_VERSION_PATTERN = re.compile(r"Python\s+(\d+)\.(\d+)(?:\.(\d+))?")
CACHE_CATEGORIES = ("osm", "elevation", "imagery")


def ortho4xp_version(script_path: Path) -> str | None:
    """Extract the Ortho4XP version string from a script name, if present."""
    match = re.search(r"v(\d+)", script_path.stem, re.IGNORECASE)
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 1:
        return f"{digits}.0"
    if len(digits) == 2:
        return f"{digits[0]}.{digits[1]}"
    return f"{digits[0]}.{digits[1:]}"


def parse_python_version(output: str) -> tuple[int, int, int] | None:
    """Parse a Python version tuple from a `python --version` string."""
    match = PYTHON_VERSION_PATTERN.search(output)
    if not match:
        return None
    major, minor, patch = match.group(1), match.group(2), match.group(3) or "0"
    return int(major), int(minor), int(patch)


def resolve_python_executable(python_exe: str | None) -> str | None:
    """Resolve a Python executable path for Ortho4XP."""
    if not python_exe:
        return sys.executable
    candidate = Path(python_exe)
    if candidate.exists():
        return str(candidate)
    return shutil.which(python_exe)


def probe_python_runtime(
    python_exe: str | None,
) -> tuple[str | None, tuple[int, int, int] | None, str | None]:
    """Return resolved python path, version tuple, and error (if any)."""
    resolved = resolve_python_executable(python_exe)
    if not resolved:
        return None, None, f"Python executable not found: {python_exe}"
    if not python_exe or Path(resolved).resolve() == Path(sys.executable).resolve():
        version = sys.version_info[:3]
        return resolved, (version[0], version[1], version[2]), None
    try:
        result = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return resolved, None, str(exc)
    output = (result.stdout or result.stderr).strip()
    if not output:
        return resolved, None, "python --version returned no output"
    version = parse_python_version(output)
    if not version:
        return resolved, None, f"Unrecognized Python version output: {output}"
    return resolved, version, None


def _warn_if_unexpected_version(script_path: Path) -> None:
    """Warn when the detected Ortho4XP version isn't the targeted release."""
    version = ortho4xp_version(script_path)
    if version and not version.startswith("1.4"):
        warnings.warn(
            f"Ortho4XP {version} detected; dem2dsf targets {TARGET_ORTHO4XP_VERSION}.",
            RuntimeWarning,
            stacklevel=2,
        )


def find_ortho4xp_script(root: Path) -> Path:
    """Return the Ortho4XP script path inside a root directory."""
    if not root.exists():
        raise Ortho4XPNotFoundError(f"Ortho4XP root not found: {root}")
    candidates = sorted(root.glob("Ortho4XP*.py"))
    if not candidates:
        raise Ortho4XPNotFoundError(f"No Ortho4XP script found in {root}")
    script = candidates[-1]
    _warn_if_unexpected_version(script)
    return script


def stage_custom_dem(root: Path, tile: str, dem_path: Path) -> Path:
    """Copy a tile DEM into Ortho4XP's Elevation_data folder."""
    destination = elevation_data_path(root, tile, dem_path.suffix)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stem = hgt_tile_name(tile)
    for candidate in destination.parent.glob(f"{stem}.*"):
        if candidate == destination:
            continue
        if candidate.is_file():
            candidate.unlink()
    shutil.copy(dem_path, destination)
    return destination


def build_command(
    script_path: Path,
    tile: str,
    output_dir: Path,
    *,
    python_exe: str | None = None,
    extra_args: Iterable[str] | None = None,
    include_output: bool = True,
) -> list[str]:
    """Build a command line to run Ortho4XP."""
    cmd = [python_exe or sys.executable, str(script_path)]
    supports_flags = _script_supports_flag_args(script_path)
    if supports_flags:
        if extra_args:
            cmd.extend(list(extra_args))
        cmd.extend(["--tile", tile])
        if include_output:
            cmd.extend(["--output", str(output_dir)])
        return cmd
    lat, lon = parse_tile(tile)
    cmd.extend([str(lat), str(lon)])
    if extra_args:
        cmd.extend([arg for arg in extra_args if not str(arg).startswith("-")])
    return cmd


def _script_supports_flag_args(script_path: Path) -> bool:
    try:
        content = script_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return any(flag in content for flag in ("--tile", "--batch", "--output"))


def default_scenery_root(root: Path) -> Path:
    """Return the default Custom Scenery root inside Ortho4XP."""
    return root / "Custom Scenery"


def tile_scenery_dir(scenery_root: Path, tile: str) -> Path:
    """Return the expected tile scenery directory for a tile."""
    return scenery_root / f"zOrtho4XP_{tile}"


def copy_tile_outputs(
    tile_dir: Path,
    output_dir: Path,
    *,
    include_textures: bool = False,
) -> None:
    """Copy tile outputs from Ortho4XP into a build directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    earth_nav = tile_dir / "Earth nav data"
    if earth_nav.exists():
        shutil.copytree(
            earth_nav,
            output_dir / "Earth nav data",
            dirs_exist_ok=True,
        )
    for cfg_path in tile_dir.glob("*.cfg"):
        shutil.copy(cfg_path, output_dir / cfg_path.name)
    terrain_dir = tile_dir / "terrain"
    if terrain_dir.exists():
        shutil.copytree(terrain_dir, output_dir / "terrain", dirs_exist_ok=True)
    if include_textures:
        textures_dir = tile_dir / "textures"
        if textures_dir.exists():
            shutil.copytree(
                textures_dir, output_dir / "textures", dirs_exist_ok=True
            )


def update_skip_downloads(config_path: Path, enabled: bool) -> None:
    """Set Ortho4XP skip_downloads in the config file."""
    desired = f"skip_downloads={'True' if enabled else 'False'}"
    lines: list[str] = []
    if config_path.exists():
        lines = config_path.read_text(encoding="utf-8").splitlines()
    found = False
    for index, line in enumerate(lines):
        if line.strip().startswith("skip_downloads"):
            lines[index] = desired
            found = True
            break
    if not found:
        lines.append(desired)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ortho_cache_roots(root: Path) -> dict[str, Path]:
    """Return the Ortho4XP cache roots keyed by cache category."""
    return {
        "osm": root / "OSM_data",
        "elevation": root / "Elevation_data",
        "imagery": root / "Orthophotos",
    }


def find_tile_cache_entries(
    root: Path,
    tile: str,
    *,
    categories: Iterable[str] | None = None,
) -> dict[str, list[Path]]:
    """Locate Ortho4XP cache entries that appear to belong to a tile."""
    selected = set(categories or CACHE_CATEGORIES)
    results: dict[str, list[Path]] = {key: [] for key in selected}
    cache_roots = ortho_cache_roots(root)
    if "elevation" in selected:
        bucket = bucket_for_tile(tile)
        elevation_dir = cache_roots["elevation"] / bucket
        if elevation_dir.exists():
            results["elevation"] = list(
                elevation_dir.glob(f"{hgt_tile_name(tile)}.*")
            )
    if "osm" in selected:
        bucket = bucket_for_tile(tile)
        osm_dir = cache_roots["osm"] / bucket
        if osm_dir.exists():
            results["osm"] = list(osm_dir.glob(f"*{tile}*"))
    if "imagery" in selected:
        imagery_dir = cache_roots["imagery"]
        if imagery_dir.exists():
            results["imagery"] = list(imagery_dir.glob(f"*{tile}*"))
    return results


def purge_tile_cache_entries(
    root: Path,
    tile: str,
    *,
    categories: Iterable[str] | None = None,
    dry_run: bool = True,
) -> dict[str, object]:
    """Remove Ortho4XP cache entries for a tile and return the purge report."""
    entries = find_tile_cache_entries(root, tile, categories=categories)
    removed: dict[str, list[str]] = {key: [] for key in entries}
    for category, paths in entries.items():
        for path in paths:
            removed[category].append(str(path))
            if dry_run:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
    return {
        "tile": tile,
        "dry_run": dry_run,
        "entries": {key: [str(path) for path in paths] for key, paths in entries.items()},
        "removed": removed,
    }


def patch_config_values(
    config_path: Path,
    updates: Mapping[str, object],
) -> str | None:
    """Patch Ortho4XP.cfg with provided key/value updates and return original."""
    if not updates:
        return None
    original = None
    lines: list[str] = []
    if config_path.exists():
        original = config_path.read_text(encoding="utf-8")
        lines = original.splitlines()
    remaining = {key: str(value) for key, value in updates.items()}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[index] = f"{key}={remaining.pop(key)}"
    for key, value in remaining.items():
        lines.append(f"{key}={value}")
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return original


def read_config_values(config_path: Path) -> dict[str, str]:
    """Read key/value pairs from Ortho4XP.cfg."""
    if not config_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def restore_config(config_path: Path, original: str | None) -> None:
    """Restore Ortho4XP.cfg to the original content (or remove if absent)."""
    if original is None:
        if config_path.exists():
            config_path.unlink()
        return
    config_path.write_text(original, encoding="utf-8")
