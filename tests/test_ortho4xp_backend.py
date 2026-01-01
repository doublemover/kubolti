from __future__ import annotations

import sys
import textwrap

import pytest

from dem2dsf.backends.base import BuildRequest
from dem2dsf.backends.ortho4xp import (
    Ortho4XPBackend,
    _normalize_runner,
    _run_runner,
    _validate_runner,
)


def test_ortho4xp_backend_runner(tmp_path) -> None:
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
    dem_path.write_text("dem", encoding="utf-8")
    tile_dem = tmp_path / "tile_dem.tif"
    tile_dem.write_text("tile", encoding="utf-8")

    output_dir = tmp_path / "build"
    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(dem_path,),
        output_dir=output_dir,
        options={
            "runner": [sys.executable, str(runner)],
            "density": "low",
            "quality": "compat",
            "tile_dem_paths": {"+47+008": str(tile_dem)},
        },
    )

    backend = Ortho4XPBackend()
    result = backend.build(request)

    assert result.build_report["tiles"][0]["status"] == "ok"
    assert result.build_report["artifacts"]["dsf_paths"]
    assert (output_dir / "used_dem.txt").read_text(encoding="utf-8") == str(tile_dem)


def test_ortho4xp_backend_autoortho_flag(tmp_path) -> None:
    runner = tmp_path / "ortho4xp_runner.py"
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
            parser.add_argument("--ortho-root")
            parser.add_argument("--autoortho", action="store_true")
            parser.add_argument("--config-json")
            args = parser.parse_args()

            out_path = dsf_path(Path(args.output), args.tile)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("stub", encoding="utf-8")
            if args.autoortho:
                (Path(args.output) / "autoortho.flag").write_text(
                    "true", encoding="utf-8"
                )
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")
    ortho_root = tmp_path / "ortho"
    ortho_root.mkdir()

    output_dir = tmp_path / "build"
    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(dem_path,),
        output_dir=output_dir,
        options={
            "runner": [sys.executable, str(runner), "--ortho-root", str(ortho_root)],
            "density": "low",
            "quality": "compat",
            "autoortho": True,
        },
    )

    backend = Ortho4XPBackend()
    backend.build(request)

    assert (output_dir / "autoortho.flag").exists()


def test_ortho4xp_backend_missing_runner(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")

    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(dem_path,),
        output_dir=tmp_path,
        options={"quality": "compat"},
    )

    backend = Ortho4XPBackend()
    result = backend.build(request)

    assert result.build_report["tiles"][0]["status"] == "skipped"
    assert "runner not configured" in result.build_report["tiles"][0]["messages"][0]


def test_ortho4xp_backend_missing_dem(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(),
        output_dir=tmp_path,
        options={"runner": [sys.executable, str(runner)]},
    )

    backend = Ortho4XPBackend()
    result = backend.build(request)

    assert result.build_report["tiles"][0]["status"] == "error"


def test_ortho4xp_backend_missing_dem_file(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(tmp_path / "missing.tif",),
        output_dir=tmp_path,
        options={"runner": [sys.executable, str(runner)]},
    )

    backend = Ortho4XPBackend()
    result = backend.build(request)

    tile = result.build_report["tiles"][0]
    assert tile["status"] == "error"
    assert "DEM not found" in tile["messages"][0]


def test_ortho4xp_backend_runner_error(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")

    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(dem_path,),
        output_dir=tmp_path,
        options={"runner": [sys.executable, str(runner)]},
    )

    backend = Ortho4XPBackend()
    result = backend.build(request)

    assert result.build_report["tiles"][0]["status"] == "error"


def test_ortho4xp_backend_missing_runner_binary(tmp_path) -> None:
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")

    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(dem_path,),
        output_dir=tmp_path,
        options={"runner": ["missing-runner"]},
    )

    backend = Ortho4XPBackend()
    result = backend.build(request)

    tile = result.build_report["tiles"][0]
    assert tile["status"] == "skipped"
    assert "Runner executable not found" in tile["messages"][0]


def test_ortho4xp_backend_multiple_dems(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    dem_a = tmp_path / "a.tif"
    dem_b = tmp_path / "b.tif"
    dem_a.write_text("dem", encoding="utf-8")
    dem_b.write_text("dem", encoding="utf-8")

    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(dem_a, dem_b),
        output_dir=tmp_path,
        options={"runner": [sys.executable, str(runner)]},
    )

    backend = Ortho4XPBackend()
    result = backend.build(request)

    assert any(
        "Multiple DEMs provided" in warning
        for warning in result.build_report["warnings"]
    )


def test_ortho4xp_backend_invalid_density(tmp_path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")

    request = BuildRequest(
        tiles=("+47+008",),
        dem_paths=(dem_path,),
        output_dir=tmp_path,
        options={"runner": [sys.executable, str(runner)], "density": "bad"},
    )

    backend = Ortho4XPBackend()
    result = backend.build(request)

    assert result.build_report["warnings"]


def test_ortho4xp_normalize_runner_string() -> None:
    assert _normalize_runner("ortho") == ["ortho"]


def test_ortho4xp_normalize_runner_invalid_type() -> None:
    with pytest.raises(TypeError, match="Runner must be a string"):
        _normalize_runner({"runner": "bad"})


def test_validate_runner_requires_root(monkeypatch, tmp_path) -> None:
    runner = tmp_path / "ortho4xp_runner.py"
    runner.write_text("stub", encoding="utf-8")
    monkeypatch.delenv("ORTHO4XP_ROOT", raising=False)
    error = _validate_runner([sys.executable, str(runner)])
    assert error and "Ortho4XP root not configured" in error


def test_validate_runner_with_root(tmp_path) -> None:
    runner = tmp_path / "ortho4xp_runner.py"
    runner.write_text("stub", encoding="utf-8")
    error = _validate_runner(
        [sys.executable, str(runner), "--ortho-root", str(tmp_path)]
    )
    assert error is None


def test_validate_runner_empty() -> None:
    assert _validate_runner([]) == "Runner command is empty."


def test_run_runner_handles_oserror(monkeypatch, tmp_path) -> None:
    def boom(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr("dem2dsf.backends.ortho4xp.run_command", boom)
    result = _run_runner(
        [sys.executable, "runner.py"],
        "+47+008",
        tmp_path / "dem.tif",
        tmp_path,
    )
    assert result.returncode == 1
    assert "boom" in result.stderr
