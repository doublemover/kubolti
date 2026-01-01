from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path
from tests.utils import write_raster


def _load_script(name: str):
    module_path = Path(__file__).resolve().parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_profile_build_script_dry_run(tmp_path: Path, monkeypatch) -> None:
    module = _load_script("profile_build.py")
    profile_dir = tmp_path / "profiles"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile_build.py",
            "--dem",
            "fake.tif",
            "--tile",
            "+47+008",
            "--output",
            str(tmp_path / "build"),
            "--profile-dir",
            str(profile_dir),
            "--dry-run",
            "--summary",
        ],
    )

    assert module.main() == 0
    slug = "p47p008"
    assert (profile_dir / f"build_{slug}.pstats").exists()
    assert (profile_dir / f"build_{slug}.metrics.json").exists()
    assert (profile_dir / f"build_{slug}.txt").exists()


def test_benchmark_normalize_script(tmp_path: Path, monkeypatch) -> None:
    module = _load_script("benchmark_normalize.py")
    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        np.array([[1]], dtype=np.int16),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999,
    )
    output_dir = tmp_path / "bench"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_normalize.py",
            "--dem",
            str(dem_path),
            "--tile",
            "+47+008",
            "--runs",
            "1",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert module.main() == 0
    csv_path = output_dir / "normalize.csv"
    assert csv_path.exists()


def test_benchmark_publish_script(tmp_path: Path, monkeypatch) -> None:
    module = _load_script("benchmark_publish.py")
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")
    output_dir = tmp_path / "bench"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_publish.py",
            "--build-dir",
            str(build_dir),
            "--runs",
            "1",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert module.main() == 0
    csv_path = output_dir / "publish.csv"
    assert csv_path.exists()
    zip_path = output_dir / "run_01" / "build.zip"
    assert zip_path.exists()
