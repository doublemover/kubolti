"""XP12 raster inventory and enrichment helpers."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dem2dsf.tools.dsftool import dsftool_7z_hint, run_dsftool
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path

XP12_SEASON_EXPECTED = 8
_SEASON_TOKENS = ("season", "spring", "summer", "autumn", "fall", "winter")
_SOUND_TOKENS = ("sound", "soundscape")
_BOUND_PROPERTIES = {"sim/west", "sim/south", "sim/east", "sim/north"}


@dataclass(frozen=True)
class RasterSummary:
    """Summary of raster layers found in a DSF."""

    raster_names: tuple[str, ...]
    soundscape_present: bool
    season_raster_count: int
    season_raster_expected: int = XP12_SEASON_EXPECTED


@dataclass(frozen=True)
class EnrichmentResult:
    """Result of an XP12 raster enrichment attempt."""

    status: str
    missing: tuple[str, ...]
    added: tuple[str, ...]
    backup_path: str | None
    enriched_text_path: str | None
    error: str | None


@dataclass(frozen=True)
class RasterBlock:
    """Parsed raster block lines keyed by name and index."""

    name: str
    index: int
    lines: tuple[str, ...]


def parse_raster_names(text: str) -> list[str]:
    """Extract raster names from DSFTool text output."""
    names: list[str] = []
    quoted = re.compile(r"\"([^\"]+)\"")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "raster" not in line.lower():
            continue
        match = quoted.search(line)
        if match:
            names.append(match.group(1))
            continue
        tokens = line.split()
        for token in tokens:
            lower = token.lower().strip(",")
            if lower in {"raster", "raster_def", "raster_definition"}:
                continue
            if lower.startswith("raster_"):
                continue
            if lower.replace(".", "", 1).isdigit():
                continue
            if lower.startswith("#"):
                break
            if any(char.isalpha() for char in lower):
                names.append(token.strip().strip(","))
                break
    return list(dict.fromkeys(names))


def _parse_raster_index(tokens: list[str]) -> int | None:
    """Parse the raster index token (second token) as an int."""
    if len(tokens) < 2:
        return None
    try:
        return int(tokens[1])
    except ValueError:
        return None


def _extract_raster_blocks(text: str) -> dict[str, RasterBlock]:
    """Parse raster-related lines keyed by raster name."""
    quoted = re.compile(r"\"([^\"]+)\"")
    blocks: dict[int, dict[str, object]] = {}
    ordered: list[int] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tokens = line.split()
        if not tokens:
            continue
        keyword = tokens[0].lower()
        if keyword == "raster_def":
            index = _parse_raster_index(tokens)
            if index is None:
                continue
            match = quoted.search(line)
            if match:
                name = match.group(1)
            else:
                name = ""
                for token in tokens[1:]:
                    candidate = token.strip().strip(",")
                    if any(char.isalpha() for char in candidate):
                        name = candidate
                        break
            if not name:
                continue
            blocks[index] = {"name": name, "lines": [raw_line]}
            ordered.append(index)
            continue
        if keyword.startswith("raster_"):
            index = _parse_raster_index(tokens)
            if index is None:
                continue
            block = blocks.get(index)
            if block:
                block["lines"].append(raw_line)
    results: dict[str, RasterBlock] = {}
    for index in ordered:
        block = blocks.get(index)
        if not block:
            continue
        name = block["name"]
        lines = block["lines"]
        if isinstance(name, str) and isinstance(lines, list):
            results[name] = RasterBlock(name=name, index=index, lines=tuple(lines))
    return results


def _property_key(line: str) -> str | None:
    """Return the property key for a PROPERTY line."""
    tokens = line.strip().split()
    if len(tokens) < 3:
        return None
    if tokens[0].lower() != "property":
        return None
    return tokens[1].strip().strip('"').lower()


def _is_bound_property(line: str) -> bool:
    """Return True if the line defines a DSF tile boundary property."""
    key = _property_key(line)
    return key in _BOUND_PROPERTIES if key else False


def _rewrite_raster_lines(lines: Iterable[str], new_index: int) -> list[str]:
    """Rewrite raster lines with a new index token."""
    updated: list[str] = []
    for raw_line in lines:
        tokens = raw_line.split()
        if len(tokens) > 1 and tokens[0].lower().startswith("raster_"):
            if tokens[1].lstrip("+-").isdigit():
                tokens[1] = str(new_index)
                raw_line = " ".join(tokens)
        updated.append(raw_line)
    return updated


def _collect_raw_sidecars(text_path: Path) -> list[Path]:
    """Collect raw sidecar files produced by DSFTool for a text path."""
    return sorted(text_path.parent.glob(f"{text_path.name}.*.raw"))


def _copy_raw_sidecars(
    *,
    source_text: Path,
    dest_text: Path,
    missing_names: Iterable[str],
    index_map: dict[int, int],
) -> None:
    """Copy DSFTool raw sidecars, renaming to match the destination text."""
    sidecars = _collect_raw_sidecars(source_text)
    if not sidecars:
        return
    missing_tokens = {name.lower() for name in missing_names}
    matched = [
        path for path in sidecars if any(token in path.name.lower() for token in missing_tokens)
    ]
    candidates = matched or sidecars
    for src in candidates:
        suffix = src.name[len(source_text.name) :]
        dest_name = f"{dest_text.name}{suffix}"
        for old, new in index_map.items():
            dest_name = dest_name.replace(f".{old}.", f".{new}.")
            if dest_name.endswith(f".{old}.raw"):
                dest_name = dest_name[: -len(f".{old}.raw")] + f".{new}.raw"
        dest = dest_text.with_name(dest_name)
        if dest.exists():
            continue
        shutil.copy(src, dest)


def _is_xp12_raster(name: str) -> bool:
    """Return True if a raster name matches XP12 tokens."""
    lower = name.lower()
    return any(token in lower for token in (*_SOUND_TOKENS, *_SEASON_TOKENS))


def summarize_rasters(names: Iterable[str]) -> RasterSummary:
    """Summarize raster names and XP12 coverage."""
    normalized = [name.strip() for name in names if name.strip()]
    soundscape_present = any(
        any(token in name.lower() for token in _SOUND_TOKENS) for name in normalized
    )
    season_rasters = [
        name for name in normalized if any(token in name.lower() for token in _SEASON_TOKENS)
    ]
    return RasterSummary(
        raster_names=tuple(normalized),
        soundscape_present=soundscape_present,
        season_raster_count=len(season_rasters),
    )


def inventory_dsf_rasters(
    dsftool_path: Path,
    dsf_path: Path,
    work_dir: Path,
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> RasterSummary:
    """Run DSFTool to list raster layers in a DSF."""
    work_dir.mkdir(parents=True, exist_ok=True)
    text_path = work_dir / f"{dsf_path.stem}.txt"

    hint = dsftool_7z_hint(dsftool_path, dsf_path)
    if hint and "cannot read" in hint:
        raise RuntimeError(f"DSFTool dsf2text failed: {hint}")
    result = run_dsftool(
        dsftool_path,
        ["--dsf2text", str(dsf_path), str(text_path)],
        timeout=timeout,
        retries=retries,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "unknown error"
        if hint:
            message = f"{message} ({hint})"
        raise RuntimeError(f"DSFTool dsf2text failed: {message}")

    text = text_path.read_text(encoding="utf-8")
    names = parse_raster_names(text)
    return summarize_rasters(names)


def enrich_dsf_rasters(
    dsftool_path: Path,
    dsf_path: Path,
    global_dsf_path: Path,
    work_dir: Path,
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> EnrichmentResult:
    """Attempt to enrich a DSF with XP12 rasters from global scenery."""
    work_dir.mkdir(parents=True, exist_ok=True)
    target_text_path = work_dir / f"{dsf_path.stem}.txt"
    global_text_path = work_dir / f"{global_dsf_path.stem}.txt"
    enriched_text_path = work_dir / f"{dsf_path.stem}.enriched.txt"
    enriched_dsf_path = work_dir / f"{dsf_path.stem}.enriched.dsf"

    target_hint = dsftool_7z_hint(dsftool_path, dsf_path)
    if target_hint and "cannot read" in target_hint:
        return EnrichmentResult(
            status="failed",
            missing=tuple(),
            added=tuple(),
            backup_path=None,
            enriched_text_path=None,
            error=f"DSFTool dsf2text failed: {target_hint}",
        )
    result = run_dsftool(
        dsftool_path,
        ["--dsf2text", str(dsf_path), str(target_text_path)],
        timeout=timeout,
        retries=retries,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "unknown error"
        if target_hint:
            message = f"{message} ({target_hint})"
        return EnrichmentResult(
            status="failed",
            missing=tuple(),
            added=tuple(),
            backup_path=None,
            enriched_text_path=None,
            error=f"DSFTool dsf2text failed: {message}",
        )

    global_hint = dsftool_7z_hint(dsftool_path, global_dsf_path)
    if global_hint and "cannot read" in global_hint:
        return EnrichmentResult(
            status="failed",
            missing=tuple(),
            added=tuple(),
            backup_path=None,
            enriched_text_path=None,
            error=f"DSFTool dsf2text failed: {global_hint}",
        )
    result = run_dsftool(
        dsftool_path,
        ["--dsf2text", str(global_dsf_path), str(global_text_path)],
        timeout=timeout,
        retries=retries,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "unknown error"
        if global_hint:
            message = f"{message} ({global_hint})"
        return EnrichmentResult(
            status="failed",
            missing=tuple(),
            added=tuple(),
            backup_path=None,
            enriched_text_path=None,
            error=f"DSFTool dsf2text failed: {message}",
        )

    target_text = target_text_path.read_text(encoding="utf-8")
    global_text = global_text_path.read_text(encoding="utf-8")

    target_blocks = _extract_raster_blocks(target_text)
    global_blocks = _extract_raster_blocks(global_text)
    target_names = set(parse_raster_names(target_text))
    missing_blocks = [
        block
        for name, block in global_blocks.items()
        if name not in target_names and _is_xp12_raster(name)
    ]
    missing = [block.name for block in missing_blocks]
    if not missing:
        return EnrichmentResult(
            status="no-op",
            missing=tuple(),
            added=tuple(),
            backup_path=None,
            enriched_text_path=None,
            error=None,
        )

    target_lines = target_text.splitlines()
    insert_at = len(target_lines)
    raster_indices = [
        index
        for index, line in enumerate(target_lines)
        if line.strip().lower().startswith("raster_")
    ]
    if raster_indices:
        insert_at = raster_indices[-1] + 1
    else:
        property_indices = [
            index
            for index, line in enumerate(target_lines)
            if line.strip().lower().startswith("property")
        ]
        if property_indices:
            insert_at = property_indices[-1] + 1
    bound_indices = [index for index, line in enumerate(target_lines) if _is_bound_property(line)]
    if bound_indices:
        insert_at = min(insert_at, min(bound_indices))

    used_indices = {block.index for block in target_blocks.values()}
    next_index = max(used_indices, default=-1) + 1
    index_map: dict[int, int] = {}
    insert_lines: list[str] = []
    for block in missing_blocks:
        new_index = block.index
        if new_index in used_indices:
            new_index = next_index
            next_index += 1
            index_map[block.index] = new_index
        used_indices.add(new_index)
        insert_lines.extend(_rewrite_raster_lines(block.lines, new_index))

    target_lines[insert_at:insert_at] = insert_lines
    enriched_text_path.write_text("\n".join(target_lines) + "\n", encoding="utf-8")
    _copy_raw_sidecars(
        source_text=global_text_path,
        dest_text=enriched_text_path,
        missing_names=missing,
        index_map=index_map,
    )

    result = run_dsftool(
        dsftool_path,
        ["--text2dsf", str(enriched_text_path), str(enriched_dsf_path)],
        timeout=timeout,
        retries=retries,
    )
    if result.returncode != 0:
        return EnrichmentResult(
            status="failed",
            missing=tuple(missing),
            added=tuple(),
            backup_path=None,
            enriched_text_path=str(enriched_text_path),
            error=f"DSFTool text2dsf failed: {result.stderr.strip()}",
        )

    backup_path = dsf_path.with_suffix(".original.dsf")
    if not backup_path.exists():
        shutil.copy(dsf_path, backup_path)
    shutil.copy(enriched_dsf_path, dsf_path)
    return EnrichmentResult(
        status="enriched",
        missing=tuple(missing),
        added=tuple(missing),
        backup_path=str(backup_path),
        enriched_text_path=str(enriched_text_path),
        error=None,
    )


def find_global_dsf(global_scenery_root: Path, tile: str) -> Path | None:
    """Locate a global scenery DSF for a tile."""
    candidate = xplane_dsf_path(global_scenery_root, tile)
    return candidate if candidate.exists() else None
