"""Tool discovery configuration helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

ENV_TOOL_PATHS = "DEM2DSF_TOOL_PATHS"


def _default_candidate_paths() -> list[Path]:
    """Return default tool config locations in priority order."""
    repo_root = Path(__file__).resolve().parents[3]
    return [
        Path.cwd() / "tools" / "tool_paths.json",
        repo_root / "tools" / "tool_paths.json",
    ]


def _load_candidate(candidate: Path) -> dict[str, Path] | None:
    """Load a tool config from a single candidate path."""
    if not candidate.exists():
        return None
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, Path] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = Path(value)
    return result


def load_tool_paths(path: Path | None = None) -> dict[str, Path]:
    """Load tool paths from JSON config, if available."""
    if path:
        return _load_candidate(path) or {}
    env_path = os.environ.get(ENV_TOOL_PATHS)
    if env_path:
        return _load_candidate(Path(env_path)) or {}
    for candidate in _default_candidate_paths():
        result = _load_candidate(candidate)
        if result is not None:
            return result
    return {}


def ortho_root_from_paths(tool_paths: dict[str, Path]) -> Path | None:
    """Return the Ortho4XP root directory from a tool paths mapping."""
    script_path = tool_paths.get("ortho4xp")
    if not script_path:
        return None
    return script_path.parent
