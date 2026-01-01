"""AutoOrtho terrain texture inspection helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_AUTOORTHO_PATTERN = re.compile(r"^\d+_\d+_[A-Za-z0-9]+_\d+\.dds$", re.IGNORECASE)


@dataclass(frozen=True)
class AutoOrthoReport:
    """Summary of texture references found in terrain files."""

    referenced: tuple[str, ...]
    missing: tuple[str, ...]
    invalid: tuple[str, ...]


def _extract_texture_refs(text: str) -> list[str]:
    """Extract texture references from a .ter file body."""
    refs: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if ".dds" not in line.lower():
            continue
        token = line.split()[-1].strip("\"")
        if token.lower().endswith(".dds"):
            refs.append(token)
    return refs


def scan_terrain_textures(scenery_dir: Path) -> AutoOrthoReport:
    """Scan terrain files for texture references and validate naming."""
    referenced: list[str] = []
    missing: list[str] = []
    invalid: list[str] = []

    for terrain_path in scenery_dir.rglob("*.ter"):
        try:
            text = terrain_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for ref in _extract_texture_refs(text):
            referenced.append(ref)
            name = Path(ref).name
            if not _AUTOORTHO_PATTERN.match(name):
                invalid.append(ref)
            ref_path = Path(ref)
            candidate = ref_path if ref_path.is_absolute() else scenery_dir / ref_path
            if not candidate.exists():
                missing.append(ref)

    return AutoOrthoReport(
        referenced=tuple(dict.fromkeys(referenced)),
        missing=tuple(dict.fromkeys(missing)),
        invalid=tuple(dict.fromkeys(invalid)),
    )
