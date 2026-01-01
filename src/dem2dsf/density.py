"""Density presets for backends and triangle guardrails."""

from __future__ import annotations

from typing import Dict

DENSITY_PRESETS: Dict[str, Dict[str, float]] = {
    "low": {"curvature_tol": 3.0, "mesh_zl": 16.0},
    "medium": {"curvature_tol": 2.0, "mesh_zl": 17.0},
    "high": {"curvature_tol": 1.0, "mesh_zl": 18.0},
    "ultra": {"curvature_tol": 0.5, "mesh_zl": 19.0},
}

DENSITY_TRIANGLE_LIMITS: Dict[str, Dict[str, int]] = {
    "low": {"warn": 1_000_000, "max": 3_000_000},
    "medium": {"warn": 1_500_000, "max": 5_000_000},
    "high": {"warn": 2_500_000, "max": 7_500_000},
    "ultra": {"warn": 4_000_000, "max": 12_000_000},
}



def ortho4xp_config_for_preset(preset: str) -> Dict[str, float]:
    """Return Ortho4XP config values for a density preset."""
    if preset not in DENSITY_PRESETS:
        raise ValueError(f"Unknown density preset: {preset}")
    return dict(DENSITY_PRESETS[preset])


def triangle_limits_for_preset(preset: str) -> Dict[str, int]:
    """Return warning and max triangle thresholds for a preset."""
    if preset not in DENSITY_TRIANGLE_LIMITS:
        raise ValueError(f"Unknown density preset: {preset}")
    return dict(DENSITY_TRIANGLE_LIMITS[preset])
