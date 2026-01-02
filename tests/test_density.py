from __future__ import annotations

import pytest

from dem2dsf.density import ortho4xp_config_for_preset, triangle_limits_for_preset


def test_density_mapping() -> None:
    config = ortho4xp_config_for_preset("medium")
    assert "curvature_tol" in config


def test_density_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown density preset"):
        ortho4xp_config_for_preset("hyper")

    with pytest.raises(ValueError, match="Unknown density preset"):
        triangle_limits_for_preset("hyper")


def test_triangle_limits() -> None:
    limits = triangle_limits_for_preset("medium")
    assert limits["warn"] < limits["max"]


def test_ultra_preset_limits() -> None:
    config = ortho4xp_config_for_preset("ultra")
    assert config["mesh_zl"] == 19.0
    limits = triangle_limits_for_preset("ultra")
    assert limits["warn"] < limits["max"]
