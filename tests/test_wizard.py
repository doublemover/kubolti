from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from dem2dsf.wizard import (
    _prompt_bool,
    _prompt_choice,
    _prompt_command,
    _prompt_list,
    _prompt_optional_float,
    _prompt_optional_int,
    _prompt_optional_str,
    run_wizard,
)
from tests.utils import write_raster


def test_wizard_defaults(tmp_path) -> None:
    output_dir = tmp_path / "wizard"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "wizard",
            "--dem",
            "fake.tif",
            "--tile",
            "+47+008",
            "--output",
            str(output_dir),
            "--defaults",
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (output_dir / "build_plan.json").exists()
    assert (output_dir / "build_report.json").exists()


def test_wizard_interactive(monkeypatch, tmp_path) -> None:
    inputs = iter(
        [
            "",  # stack path
            "dem.tif",
            "",  # aoi path
            "+47+008",
            "",  # output dir
            "",  # runner override
            "",  # dsftool override
            "",  # runner timeout
            "",  # runner retries
            "",  # runner stream logs
            "",  # persist config
            "",  # dsftool timeout
            "",  # dsftool retries
            "",  # quality
            "",  # density
            "",  # autoortho
            "",  # skip normalize
            "",  # target crs
            "nearest",
            "30",
            "",
            "constant",
            "5",
            "",  # mosaic strategy
            "",  # tile jobs
            "",  # continue on error
            "",  # coverage metrics
            "",  # coverage min
            "",  # triangle warn
            "",  # triangle max
            "",  # allow triangle overage
            "",  # global scenery
            "",  # profile
            "",  # bundle diagnostics
            "",  # dry run
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    output_dir = tmp_path / "wizard"
    run_wizard(
        dem_paths=None,
        tiles=None,
        output_dir=output_dir,
        options={"dry_run": True, "quality": "compat", "density": "medium"},
        defaults=False,
    )

    assert (output_dir / "build_plan.json").exists()
    assert (output_dir / "build_report.json").exists()


def test_wizard_interactive_stack(monkeypatch, tmp_path) -> None:
    layer_path = tmp_path / "layer.tif"
    write_raster(
        layer_path,
        np.ones((2, 2), dtype=np.int16),
        bounds=(0.0, 0.0, 1.0, 1.0),
        nodata=-9999,
    )
    stack_path = tmp_path / "stack.json"
    stack_path.write_text(
        json.dumps({"layers": [{"path": str(layer_path), "priority": 0}]}),
        encoding="utf-8",
    )
    inputs = iter(
        [
            str(stack_path),
            "",  # aoi path
            "+47+008",
            "",  # output dir
            "",  # runner override
            "",  # dsftool override
            "",  # runner timeout
            "",  # runner retries
            "",  # runner stream logs
            "",  # persist config
            "",  # dsftool timeout
            "",  # dsftool retries
            "",  # quality
            "",  # density
            "",  # autoortho
            "",  # skip normalize
            "",  # target crs
            "",  # resampling
            "",  # target resolution
            "",  # dst nodata
            "",  # fill strategy
            "",  # mosaic strategy
            "",  # tile jobs
            "",  # continue on error
            "",  # coverage metrics
            "",  # coverage min
            "",  # triangle warn
            "",  # triangle max
            "",  # allow triangle overage
            "",  # global scenery
            "",  # profile
            "",  # bundle diagnostics
            "",  # dry run
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    output_dir = tmp_path / "wizard_stack"
    run_wizard(
        dem_paths=None,
        tiles=None,
        output_dir=output_dir,
        options={"dry_run": True, "quality": "compat", "density": "medium"},
        defaults=False,
    )

    assert (output_dir / "build_plan.json").exists()


def test_wizard_interactive_applies_options(monkeypatch, tmp_path) -> None:
    inputs = iter(
        [
            "",  # stack path
            "dem.tif",
            "",  # aoi path
            "+47+008",
            "custom_out",
            "python runner.py --demo",
            "dsftool.exe",
            "120",
            "2",
            "y",
            "y",
            "30",
            "3",
            "xp12-enhanced",
            "high",
            "y",
            "n",
            "",  # target crs
            "",  # resampling
            "",  # target resolution
            "1",
            "none",
            "per-tile",
            "4",
            "y",
            "y",
            "0.9",
            "y",
            "123",
            "456",
            "y",
            "Global Scenery",
            "y",
            "y",
            "metrics.json",
            "y",
            "n",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    captured = {}

    def fake_run_build(**kwargs):
        captured.update(kwargs.get("options", {}))
        captured["output_dir"] = kwargs.get("output_dir")

    monkeypatch.setattr("dem2dsf.wizard.run_build", fake_run_build)

    run_wizard(
        dem_paths=None,
        tiles=None,
        output_dir=tmp_path,
        options={"dry_run": True, "quality": "compat", "density": "medium"},
        defaults=False,
    )

    assert captured["output_dir"] == Path("custom_out")
    assert captured["quality"] == "xp12-enhanced"
    assert captured["density"] == "high"
    assert captured["autoortho"] is True
    assert captured["normalize"] is True
    assert captured["runner"][:3] == ["python", "runner.py", "--demo"]
    assert captured["dsftool"] == ["dsftool.exe"]
    assert captured["dst_nodata"] == 1.0
    assert captured["tile_jobs"] == 4
    assert captured["triangle_warn"] == 123
    assert captured["triangle_max"] == 456
    assert captured["allow_triangle_overage"] is True
    assert captured["mosaic_strategy"] == "per-tile"
    assert captured["continue_on_error"] is True
    assert captured["coverage_metrics"] is True
    assert captured["coverage_min"] == 0.9
    assert captured["coverage_hard_fail"] is True
    assert captured["runner_timeout"] == 120.0
    assert captured["runner_retries"] == 2
    assert captured["runner_stream_logs"] is True
    assert "--persist-config" in captured["runner"]
    assert captured["dsftool_timeout"] == 30.0
    assert captured["dsftool_retries"] == 3
    assert captured["global_scenery"] == "Global Scenery"
    assert captured["enrich_xp12"] is True
    assert captured["profile"] is True
    assert captured["metrics_json"] == "metrics.json"
    assert captured["bundle_diagnostics"] is True
    assert captured["dry_run"] is False


def test_prompt_helpers(monkeypatch) -> None:
    inputs = iter(["bad", "nearest"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    assert _prompt_choice("Resampling", ("nearest", "bilinear"), "nearest") == "nearest"

    inputs = iter(["oops", "42"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    assert _prompt_optional_float("Resolution", 10.0) == 42.0

    inputs = iter(["oops", "5"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    assert _prompt_optional_int("Tile workers", 1) == 5

    inputs = iter(["", "value"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    assert _prompt_optional_str("Target CRS", "EPSG:4326") == "EPSG:4326"
    assert _prompt_optional_str("Target CRS", None) == "value"

    inputs = iter(["a, b, c"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    assert _prompt_list("Tiles") == ["a", "b", "c"]

    inputs = iter(["y", "n", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    assert _prompt_bool("AutoOrtho", False) is True
    assert _prompt_bool("AutoOrtho", True) is False
    assert _prompt_bool("AutoOrtho", True) is True

    inputs = iter(["python runner.py --demo"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    assert _prompt_command("Runner", None) == ["python", "runner.py", "--demo"]


def test_wizard_defaults_requires_tile(tmp_path) -> None:
    with pytest.raises(ValueError, match="Defaults mode requires --tile values or --infer-tiles"):
        run_wizard(
            dem_paths=["dem.tif"],
            tiles=None,
            output_dir=tmp_path,
            options={},
            defaults=True,
        )


def test_wizard_defaults_requires_dem(tmp_path) -> None:
    with pytest.raises(ValueError, match="Defaults mode requires --dem"):
        run_wizard(
            dem_paths=None,
            tiles=["+47+008"],
            output_dir=tmp_path,
            options={},
            defaults=True,
        )


def test_wizard_fallback_requires_paths(monkeypatch, tmp_path) -> None:
    inputs = iter(
        [
            "",  # stack path
            "dem.tif",
            "",  # aoi path
            "+47+008",
            "",  # output dir
            "",  # runner override
            "",  # dsftool override
            "",  # runner timeout
            "",  # runner retries
            "",  # runner stream logs
            "",  # persist config
            "",  # dsftool timeout
            "",  # dsftool retries
            "",  # quality
            "",  # density
            "",  # autoortho
            "",  # skip normalize
            "EPSG:4326",
            "nearest",
            "",
            "",
            "fallback",
            "",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    with pytest.raises(ValueError, match="Fallback strategy requires fallback"):
        run_wizard(
            dem_paths=None,
            tiles=None,
            output_dir=tmp_path,
            options={"dry_run": True, "quality": "compat", "density": "medium"},
            defaults=False,
        )


def test_wizard_defaults_runs_build(monkeypatch, tmp_path) -> None:
    called = {"ok": False}

    def fake_run_build(**_kwargs):
        called["ok"] = True

    monkeypatch.setattr("dem2dsf.wizard.run_build", fake_run_build)

    run_wizard(
        dem_paths=["dem.tif"],
        tiles=["+47+008"],
        output_dir=tmp_path,
        options={},
        defaults=True,
    )

    assert called["ok"] is True


def test_wizard_requires_tiles(monkeypatch, tmp_path) -> None:
    inputs = iter(["", "dem.tif", "", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    with pytest.raises(ValueError, match="Wizard requires tiles"):
        run_wizard(
            dem_paths=None,
            tiles=None,
            output_dir=tmp_path,
            options={"dry_run": True, "quality": "compat", "density": "medium"},
            defaults=False,
        )


def test_wizard_requires_dem_or_stack(monkeypatch, tmp_path) -> None:
    inputs = iter(["", "", "+47+008"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))

    with pytest.raises(ValueError, match="Wizard requires DEMs or a DEM stack"):
        run_wizard(
            dem_paths=None,
            tiles=None,
            output_dir=tmp_path,
            options={"dry_run": True, "quality": "compat", "density": "medium"},
            defaults=False,
        )
