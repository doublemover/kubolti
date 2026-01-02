from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path
from tests.utils import with_src_env, write_raster

pytestmark = pytest.mark.e2e


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_cli(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "dem2dsf", *args],
        cwd=cwd,
        env=with_src_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return result


def _write_demo_dem(path: Path, *, nodata: float | None = None) -> None:
    data = np.array([[100.0, 101.0], [102.0, 103.0]], dtype="float32")
    write_raster(path, data, bounds=(8.0, 47.0, 9.0, 48.0), nodata=nodata)


def _write_stub_runner(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "import argparse",
                "from pathlib import Path",
                "from dem2dsf.xplane_paths import dsf_path",
                "",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--tile', required=True)",
                "parser.add_argument('--dem', required=True)",
                "parser.add_argument('--output', required=True)",
                "parser.add_argument('--mesh-specs', nargs=2)",
                "args, _ = parser.parse_known_args()",
                "",
                "out_path = dsf_path(Path(args.output), args.tile)",
                "out_path.parent.mkdir(parents=True, exist_ok=True)",
                "out_path.write_text('dsf', encoding='utf-8')",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_e2e_build_publish_ortho4xp(tmp_path: Path) -> None:
    repo_root = _repo_root()
    dem_path = tmp_path / "dem.tif"
    _write_demo_dem(dem_path, nodata=-9999.0)

    runner_path = _write_stub_runner(tmp_path / "runner.py")
    build_dir = tmp_path / "build"

    _run_cli(
        [
            "build",
            "--dem",
            str(dem_path),
            "--tile",
            "+47+008",
            "--runner",
            sys.executable,
            str(runner_path),
            "--output",
            str(build_dir),
        ],
        cwd=repo_root,
    )

    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    assert dsf_path.exists()
    assert (build_dir / "build_plan.json").exists()
    assert (build_dir / "build_report.json").exists()

    output_zip = tmp_path / "build.zip"
    _run_cli(
        [
            "publish",
            "--build-dir",
            str(build_dir),
            "--output",
            str(output_zip),
        ],
        cwd=repo_root,
    )
    assert output_zip.exists()
    assert (build_dir / "manifest.json").exists()
    assert (build_dir / "audit_report.json").exists()


def test_e2e_patch_and_overlay(tmp_path: Path) -> None:
    repo_root = _repo_root()
    dem_path = tmp_path / "dem.tif"
    _write_demo_dem(dem_path, nodata=-9999.0)

    runner_path = _write_stub_runner(tmp_path / "runner.py")
    build_dir = tmp_path / "build"

    _run_cli(
        [
            "build",
            "--dem",
            str(dem_path),
            "--tile",
            "+47+008",
            "--runner",
            sys.executable,
            str(runner_path),
            "--output",
            str(build_dir),
        ],
        cwd=repo_root,
    )

    patch_dem = tmp_path / "patch_dem.tif"
    _write_demo_dem(patch_dem, nodata=-9999.0)
    patch_plan = tmp_path / "patch_plan.json"
    patch_plan.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "patches": [{"tile": "+47+008", "dem": str(patch_dem)}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    patch_dir = tmp_path / "patched"
    _run_cli(
        [
            "patch",
            "--build-dir",
            str(build_dir),
            "--patch",
            str(patch_plan),
            "--output",
            str(patch_dir),
            "--runner",
            sys.executable,
            str(runner_path),
        ],
        cwd=repo_root,
    )
    assert (patch_dir / "patch_report.json").exists()
    assert (patch_dir / "normalized" / "tiles" / "+47+008" / "+47+008.tif").exists()

    terrain_dir = build_dir / "terrain"
    terrain_dir.mkdir(parents=True, exist_ok=True)
    (terrain_dir / "demo.ter").write_text("TEXTURE foo.dds\n", encoding="utf-8")
    texture_path = tmp_path / "overlay.dds"
    texture_path.write_text("texture", encoding="utf-8")
    overlay_dir = tmp_path / "overlay"
    _run_cli(
        [
            "overlay",
            "--build-dir",
            str(build_dir),
            "--texture",
            str(texture_path),
            "--output",
            str(overlay_dir),
        ],
        cwd=repo_root,
    )
    overlay_terrain = overlay_dir / "terrain" / "demo.ter"
    assert overlay_terrain.exists()
    assert "../textures/overlay.dds" in overlay_terrain.read_text(encoding="utf-8")
    assert (overlay_dir / "overlay_report.json").exists()


def test_e2e_build_infers_tiles(tmp_path: Path) -> None:
    repo_root = _repo_root()
    dem_path = tmp_path / "dem.tif"
    _write_demo_dem(dem_path, nodata=-9999.0)

    runner_path = _write_stub_runner(tmp_path / "runner.py")
    build_dir = tmp_path / "build"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "build",
            "--dem",
            str(dem_path),
            "--infer-tiles",
            "--runner",
            sys.executable,
            str(runner_path),
            "--output",
            str(build_dir),
        ],
        cwd=repo_root,
        env=with_src_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert xplane_dsf_path(build_dir, "+47+008").exists()


def test_e2e_build_with_aoi(tmp_path: Path) -> None:
    repo_root = _repo_root()
    dem_path = tmp_path / "dem.tif"
    _write_demo_dem(dem_path, nodata=-9999.0)
    aoi_path = tmp_path / "aoi.json"
    aoi_path.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [8.0, 47.0],
                        [9.0, 47.0],
                        [9.0, 48.0],
                        [8.0, 48.0],
                        [8.0, 47.0],
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )
    runner_path = _write_stub_runner(tmp_path / "runner.py")
    build_dir = tmp_path / "build"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "build",
            "--dem",
            str(dem_path),
            "--aoi",
            str(aoi_path),
            "--infer-tiles",
            "--runner",
            sys.executable,
            str(runner_path),
            "--output",
            str(build_dir),
        ],
        cwd=repo_root,
        env=with_src_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_e2e_publish_modes(tmp_path: Path) -> None:
    repo_root = _repo_root()
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "build_plan.json").write_text("{}", encoding="utf-8")
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
            "--mode",
            "scenery",
        ],
        cwd=repo_root,
        env=with_src_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert output_zip.exists()

    output_zip_full = tmp_path / "build_full.zip"
    result_full = subprocess.run(
        [
            sys.executable,
            "-m",
            "dem2dsf",
            "publish",
            "--build-dir",
            str(build_dir),
            "--output",
            str(output_zip_full),
            "--mode",
            "full",
        ],
        cwd=repo_root,
        env=with_src_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result_full.returncode == 0, (
        f"stdout:\n{result_full.stdout}\nstderr:\n{result_full.stderr}"
    )
    assert output_zip_full.exists()
