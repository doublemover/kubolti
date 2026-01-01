from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import numpy as np

from dem2dsf.build import run_build
from tests.utils import write_raster


def test_run_build_dry_run(tmp_path) -> None:
    output_dir = tmp_path / "out"
    result = run_build(
        dem_paths=[Path("fake.tif")],
        tiles=["+47+008"],
        backend_name="ortho4xp",
        output_dir=output_dir,
        options={"dry_run": True, "quality": "compat", "density": "medium"},
    )

    assert result.build_plan["tiles"] == ["+47+008"]
    assert (output_dir / "build_plan.json").exists()
    assert (output_dir / "build_report.json").exists()


def test_run_build_dry_run_dem_stack(tmp_path) -> None:
    stack_path = tmp_path / "stack.json"
    layer_path = tmp_path / "layer.tif"
    layer_path.write_text("stub", encoding="utf-8")
    stack_path.write_text(
        json.dumps({"layers": [{"path": str(layer_path), "priority": 0}]}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    result = run_build(
        dem_paths=[],
        tiles=["+47+008"],
        backend_name="ortho4xp",
        output_dir=output_dir,
        options={
            "dry_run": True,
            "quality": "compat",
            "density": "medium",
            "dem_stack_path": str(stack_path),
        },
    )

    assert str(layer_path) in result.build_plan["inputs"]["dems"]
    assert (output_dir / "build_plan.json").exists()


def test_run_build_normalizes(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text(
        textwrap.dedent(
            """
            import argparse
            from pathlib import Path
            from dem2dsf.xplane_paths import dsf_path

            parser = argparse.ArgumentParser()
            parser.add_argument("--tile", required=True)
            parser.add_argument("--dem", required=True)
            parser.add_argument("--output", required=True)
            args = parser.parse_args()

            out_path = dsf_path(Path(args.output), args.tile)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("stub", encoding="utf-8")
            (Path(args.output) / "used_dem.txt").write_text(args.dem, encoding="utf-8")
            """
        ).strip()
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
    result = run_build(
        dem_paths=[dem_path],
        tiles=["+47+008"],
        backend_name="ortho4xp",
        output_dir=output_dir,
        options={
            "dry_run": False,
            "quality": "compat",
            "density": "medium",
            "runner": [sys.executable, str(runner)],
        },
    )

    assert result.build_report["tiles"][0]["status"] in {"ok", "warning"}
    coverage = result.build_report["tiles"][0]["metrics"]["coverage"]
    assert coverage["strategy"] == "none"
    normalized = output_dir / "normalized" / "tiles" / "+47+008" / "+47+008.tif"
    assert normalized.exists()
    assert (output_dir / "used_dem.txt").read_text(encoding="utf-8") == str(normalized)


def test_run_build_xp12_checks(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text(
        textwrap.dedent(
            """
            import argparse
            from pathlib import Path
            from dem2dsf.xplane_paths import dsf_path

            parser = argparse.ArgumentParser()
            parser.add_argument("--tile", required=True)
            parser.add_argument("--dem", required=True)
            parser.add_argument("--output", required=True)
            args = parser.parse_args()

            out_path = dsf_path(Path(args.output), args.tile)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("stub", encoding="utf-8")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    dsftool = tmp_path / "dsftool.py"
    dsftool.write_text(
        textwrap.dedent(
            """
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            if "--dsf2text" in args:
                out_path = Path(args[-1])
                out_path.write_text(
                    "RASTER_DEF 0 \\"soundscape\\"\\nRASTER_DEF 1 \\"season_spring_start\\"\\n",
                    encoding="utf-8",
                )
            else:
                sys.exit(1)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        np.array([[1, 2], [3, 4]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )

    output_dir = tmp_path / "out"
    result = run_build(
        dem_paths=[dem_path],
        tiles=["+47+008"],
        backend_name="ortho4xp",
        output_dir=output_dir,
        options={
            "dry_run": False,
            "quality": "xp12-enhanced",
            "density": "medium",
            "runner": [sys.executable, str(runner)],
            "dsftool": [str(dsftool)],
            "triangle_warn": 1,
            "triangle_max": 10,
        },
    )

    tile_report = result.build_report["tiles"][0]
    metrics = tile_report.get("metrics", {})
    assert "xp12_rasters" in metrics
    assert metrics["xp12_rasters"]["soundscape_present"] is True
    assert "triangles" in metrics


def test_run_build_records_performance(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text(
        textwrap.dedent(
            """
            import argparse
            from pathlib import Path
            from dem2dsf.xplane_paths import dsf_path

            parser = argparse.ArgumentParser()
            parser.add_argument("--tile", required=True)
            parser.add_argument("--dem", required=True)
            parser.add_argument("--output", required=True)
            args = parser.parse_args()

            out_path = dsf_path(Path(args.output), args.tile)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("stub", encoding="utf-8")
            """
        ).strip()
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

    metrics_path = tmp_path / "metrics.json"
    output_dir = tmp_path / "out"
    result = run_build(
        dem_paths=[dem_path],
        tiles=["+47+008"],
        backend_name="ortho4xp",
        output_dir=output_dir,
        options={
            "dry_run": False,
            "quality": "compat",
            "density": "medium",
            "runner": [sys.executable, str(runner)],
            "profile": True,
            "metrics_json": str(metrics_path),
        },
    )

    assert "performance" in result.build_report
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "spans" in metrics
    assert "backend" in metrics["spans"]


def test_run_build_dsf_validation(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text(
        textwrap.dedent(
            """
            import argparse
            from pathlib import Path
            from dem2dsf.xplane_paths import dsf_path

            parser = argparse.ArgumentParser()
            parser.add_argument("--tile", required=True)
            parser.add_argument("--dem", required=True)
            parser.add_argument("--output", required=True)
            args = parser.parse_args()

            out_path = dsf_path(Path(args.output), args.tile)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("stub", encoding="utf-8")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    dsftool = tmp_path / "dsftool.py"
    dsftool.write_text(
        textwrap.dedent(
            """
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            if "--dsf2text" in args:
                out_path = Path(args[-1])
                out_path.write_text(
                    "\\n".join(
                        [
                            "PROPERTY sim/west 8",
                            "PROPERTY sim/south 47",
                            "PROPERTY sim/east 9",
                            "PROPERTY sim/north 48",
                        ]
                    ),
                    encoding="utf-8",
                )
            elif "--text2dsf" in args:
                out_path = Path(args[-1])
                out_path.write_text("dsf", encoding="utf-8")
            else:
                sys.exit(1)
            """
        ).strip()
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
    result = run_build(
        dem_paths=[dem_path],
        tiles=["+47+008"],
        backend_name="ortho4xp",
        output_dir=output_dir,
        options={
            "dry_run": False,
            "quality": "compat",
            "density": "medium",
            "runner": [sys.executable, str(runner)],
            "dsftool": [str(dsftool)],
        },
    )

    tile_report = result.build_report["tiles"][0]
    metrics = tile_report.get("metrics", {})
    assert metrics["dsf_validation"]["roundtrip"] == "ok"
    assert metrics["dsf_validation"]["bounds"]["mismatches"] == []


def test_run_build_provenance_basic(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")
    output_dir = tmp_path / "out"

    result = run_build(
        dem_paths=[dem_path],
        tiles=["+47+008"],
        backend_name="ortho4xp",
        output_dir=output_dir,
        options={
            "dry_run": True,
            "quality": "compat",
            "density": "medium",
            "provenance_level": "basic",
        },
    )

    provenance = result.build_plan["provenance"]
    dem_entry = provenance["inputs"]["dems"][0]
    assert provenance["level"] == "basic"
    assert "size" in dem_entry
    assert "sha256" not in dem_entry


def test_run_build_stable_metadata_omits_created_at(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")
    output_dir = tmp_path / "out"

    result = run_build(
        dem_paths=[dem_path],
        tiles=["+47+008"],
        backend_name="ortho4xp",
        output_dir=output_dir,
        options={
            "dry_run": True,
            "quality": "compat",
            "density": "medium",
            "stable_metadata": True,
        },
    )

    assert "created_at" not in result.build_plan
    assert "created_at" not in result.build_report
