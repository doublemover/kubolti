from __future__ import annotations

import json
import runpy
import subprocess
import sys
from zipfile import ZipFile

import numpy as np
import pytest

from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path
from tests.utils import write_raster


def test_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dem2dsf", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "DEM2DSF" in result.stdout


def test_cli_build_dry_run(tmp_path) -> None:
    output_dir = tmp_path / "build"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "build",
            "--dem",
            "fake.tif",
            "--tile",
            "+47+008",
            "--output",
            str(output_dir),
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (output_dir / "build_plan.json").exists()
    assert (output_dir / "build_report.json").exists()


def test_cli_build_dry_run_dem_stack(tmp_path) -> None:
    output_dir = tmp_path / "build"
    stack_path = tmp_path / "stack.json"
    layer_path = tmp_path / "layer.tif"
    layer_path.write_text("stub", encoding="utf-8")
    stack_path.write_text(
        json.dumps({"layers": [{"path": str(layer_path), "priority": 0}]}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "build",
            "--dem-stack",
            str(stack_path),
            "--tile",
            "+47+008",
            "--output",
            str(output_dir),
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    plan = json.loads((output_dir / "build_plan.json").read_text(encoding="utf-8"))
    assert str(layer_path) in plan["inputs"]["dems"]


def test_cli_patch_dry_run(tmp_path) -> None:
    build_dir = tmp_path / "build"
    base_tile = build_dir / "normalized" / "tiles" / "+47+008" / "+47+008.tif"
    write_raster(
        base_tile,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    build_plan = {
        "schema_version": "1.1",
        "backend": {"name": "ortho4xp"},
        "inputs": {"dems": ["base.tif"]},
        "options": {"tile_dem_paths": {"+47+008": str(base_tile)}},
    }
    (build_dir / "build_plan.json").write_text(json.dumps(build_plan), encoding="utf-8")

    patch_plan = tmp_path / "patch.json"
    patch_dem = tmp_path / "patch_dem.tif"
    write_raster(
        patch_dem,
        np.array([[2]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    patch_plan.write_text(
        json.dumps({"patches": [{"tile": "+47+008", "dem": str(patch_dem)}]}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "patch",
            "--build-dir",
            str(build_dir),
            "--patch",
            str(patch_plan),
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output_dir = build_dir / "patches" / patch_plan.stem
    assert (output_dir / "patch_report.json").exists()


def test_cli_overlay_drape(tmp_path) -> None:
    build_dir = tmp_path / "build"
    terrain_dir = build_dir / "terrain"
    terrain_dir.mkdir(parents=True)
    (terrain_dir / "test.ter").write_text("TEXTURE ../textures/old.dds\n", encoding="utf-8")
    texture = tmp_path / "new.dds"
    texture.write_text("dds", encoding="utf-8")
    output_dir = tmp_path / "overlay"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "overlay",
            "--build-dir",
            str(build_dir),
            "--output",
            str(output_dir),
            "--texture",
            str(texture),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (output_dir / "overlay_report.json").exists()


def test_cli_gui_invokes_launch(monkeypatch) -> None:
    from dem2dsf import cli, gui

    called = {"ok": False}

    def fake_launch() -> None:
        called["ok"] = True

    monkeypatch.setattr(gui, "launch_gui", fake_launch)

    assert cli.main(["gui"]) == 0
    assert called["ok"] is True


def test_module_entrypoint(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["dem2dsf", "version"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("dem2dsf", run_name="__main__")
    assert exc.value.code == 0


def test_cli_scan_conflicts(tmp_path) -> None:
    pack_a = tmp_path / "PackA"
    pack_b = tmp_path / "PackB"
    dsf_a = xplane_dsf_path(pack_a, "+47+008")
    dsf_b = xplane_dsf_path(pack_b, "+47+008")
    dsf_a.parent.mkdir(parents=True, exist_ok=True)
    dsf_b.parent.mkdir(parents=True, exist_ok=True)
    dsf_a.write_text("a", encoding="utf-8")
    dsf_b.write_text("b", encoding="utf-8")
    (tmp_path / "scenery_packs.ini").write_text(
        "SCENERY_PACK PackB\nSCENERY_PACK PackA\n",
        encoding="utf-8",
    )

    report_path = tmp_path / "scan.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "scan",
            "--scenery-root",
            str(tmp_path),
            "--output",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["conflicts"]


def test_cli_publish(tmp_path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    output_zip = tmp_path / "build.zip"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "publish",
            "--build-dir",
            str(build_dir),
            "--output",
            str(output_zip),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output_zip.exists()
    with ZipFile(output_zip) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert "audit_report.json" in names


def test_cli_autoortho_preset(tmp_path) -> None:
    ortho_root = tmp_path / "ortho"
    ortho_root.mkdir()
    ortho_script = ortho_root / "Ortho4XP_v140.py"
    ortho_script.write_text(
        "\n".join(
            [
                "import argparse",
                "from pathlib import Path",
                "from dem2dsf.xplane_paths import dsf_path",
                "",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--tile', required=True)",
                "args, _ = parser.parse_known_args()",
                "",
                "out_path = dsf_path(",
                "    Path('Custom Scenery') / f'zOrtho4XP_{args.tile}',",
                "    args.tile,",
                ")",
                "out_path.parent.mkdir(parents=True, exist_ok=True)",
                "out_path.write_text('dsf', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )

    output_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "autoortho",
            "--dem",
            str(dem_path),
            "--tile",
            "+47+008",
            "--ortho-root",
            str(ortho_root),
            "--output",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert xplane_dsf_path(output_dir, "+47+008").exists()
    report = json.loads((output_dir / "build_report.json").read_text(encoding="utf-8"))
    assert "autoortho" in report["artifacts"]
    config_path = ortho_root / "Ortho4XP.cfg"
    assert not config_path.exists()
