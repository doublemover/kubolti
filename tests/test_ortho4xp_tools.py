from __future__ import annotations

import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

from dem2dsf.tools.ortho4xp import (
    build_command,
    copy_tile_outputs,
    default_scenery_root,
    find_ortho4xp_script,
    find_tile_cache_entries,
    ortho4xp_version,
    ortho_cache_roots,
    parse_python_version,
    patch_config_values,
    probe_python_runtime,
    purge_tile_cache_entries,
    read_config_values,
    resolve_python_executable,
    restore_config,
    stage_custom_dem,
    tile_scenery_dir,
    update_skip_downloads,
)
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path
from dem2dsf.xplane_paths import elevation_data_path


def test_find_ortho4xp_script(tmp_path: Path) -> None:
    first = tmp_path / "Ortho4XP_v130.py"
    second = tmp_path / "Ortho4XP_v140.py"
    first.write_text("pass", encoding="utf-8")
    second.write_text("pass", encoding="utf-8")

    assert find_ortho4xp_script(tmp_path) == second


def test_find_ortho4xp_script_warns_on_version(tmp_path: Path) -> None:
    script = tmp_path / "Ortho4XP_v130.py"
    script.write_text("pass", encoding="utf-8")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        assert find_ortho4xp_script(tmp_path) == script
    assert any("targets 1.40" in str(entry.message) for entry in captured)


def test_find_ortho4xp_script_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    try:
        find_ortho4xp_script(missing)
    except Exception as exc:
        assert "root not found" in str(exc)
    else:
        raise AssertionError("Expected missing root error")


def test_find_ortho4xp_script_no_candidates(tmp_path: Path) -> None:
    try:
        find_ortho4xp_script(tmp_path)
    except Exception as exc:
        assert "No Ortho4XP script" in str(exc)
    else:
        raise AssertionError("Expected missing script error")


def test_stage_custom_dem(tmp_path: Path) -> None:
    dem = tmp_path / "tile.tif"
    dem.write_text("dem", encoding="utf-8")

    dest = stage_custom_dem(tmp_path, "+47+008", dem)
    expected = elevation_data_path(tmp_path, "+47+008", ".tif")
    assert dest == expected
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "dem"


def test_copy_tile_outputs(tmp_path: Path) -> None:
    tile_dir = tmp_path / "zOrtho4XP_+47+008"
    terrain = tile_dir / "terrain"
    textures = tile_dir / "textures"
    dsf_path = xplane_dsf_path(tile_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    terrain.mkdir()
    textures.mkdir()

    dsf_path.write_text("dsf", encoding="utf-8")
    (tile_dir / "Ortho4XP_+47+008.cfg").write_text("cfg", encoding="utf-8")
    (terrain / "tile.ter").write_text("ter", encoding="utf-8")
    (textures / "tex.dds").write_text("dds", encoding="utf-8")

    output_dir = tmp_path / "out"
    copy_tile_outputs(tile_dir, output_dir, include_textures=False)

    assert xplane_dsf_path(output_dir, "+47+008").exists()
    assert (output_dir / "Ortho4XP_+47+008.cfg").exists()
    assert (output_dir / "terrain" / "tile.ter").exists()
    assert not (output_dir / "textures" / "tex.dds").exists()

    copy_tile_outputs(tile_dir, output_dir, include_textures=True)
    assert (output_dir / "textures" / "tex.dds").exists()


def test_update_skip_downloads(tmp_path: Path) -> None:
    config = tmp_path / "Ortho4XP.cfg"
    config.write_text("existing=1\n", encoding="utf-8")

    update_skip_downloads(config, True)
    text = config.read_text(encoding="utf-8")
    assert "skip_downloads=True" in text

    update_skip_downloads(config, False)
    text = config.read_text(encoding="utf-8")
    assert "skip_downloads=False" in text


def test_read_config_values(tmp_path: Path) -> None:
    config = tmp_path / "Ortho4XP.cfg"
    config.write_text(
        'custom_overlay_src="C:/X-Plane/Global Scenery"\n'
        "foo=bar # inline\n"
        "# comment\n",
        encoding="utf-8",
    )
    values = read_config_values(config)
    assert values["custom_overlay_src"] == "C:/X-Plane/Global Scenery"
    assert values["foo"] == "bar"


def test_find_tile_cache_entries(tmp_path: Path) -> None:
    roots = ortho_cache_roots(tmp_path)
    bucket = (tmp_path / "Elevation_data" / "+40+000")
    bucket.mkdir(parents=True, exist_ok=True)
    elev = bucket / "N47E008.hgt"
    elev.write_text("dem", encoding="utf-8")
    osm_dir = roots["osm"] / "+40+000"
    osm_dir.mkdir(parents=True, exist_ok=True)
    osm_file = osm_dir / "+47+008.osm.bz2"
    osm_file.write_text("osm", encoding="utf-8")
    imagery_dir = roots["imagery"]
    imagery_dir.mkdir(parents=True, exist_ok=True)
    imagery_tile = imagery_dir / "+47+008"
    imagery_tile.mkdir()

    entries = find_tile_cache_entries(tmp_path, "+47+008")
    assert elev in entries["elevation"]
    assert osm_file in entries["osm"]
    assert imagery_tile in entries["imagery"]


def test_purge_tile_cache_entries(tmp_path: Path) -> None:
    roots = ortho_cache_roots(tmp_path)
    elev_dir = roots["elevation"] / "+40+000"
    elev_dir.mkdir(parents=True, exist_ok=True)
    elev = elev_dir / "N47E008.hgt"
    elev.write_text("dem", encoding="utf-8")
    report = purge_tile_cache_entries(tmp_path, "+47+008", dry_run=True)
    assert report["dry_run"] is True
    assert elev.exists()
    report = purge_tile_cache_entries(tmp_path, "+47+008", dry_run=False)
    assert report["dry_run"] is False
    assert not elev.exists()


def test_patch_config_values_roundtrip(tmp_path: Path) -> None:
    config = tmp_path / "Ortho4XP.cfg"
    config.write_text("curvature_tol=2.0\n", encoding="utf-8")

    original = patch_config_values(
        config,
        {"curvature_tol": 1.5, "mesh_zl": 18},
    )
    text = config.read_text(encoding="utf-8")
    assert "curvature_tol=1.5" in text
    assert "mesh_zl=18" in text

    restore_config(config, original)
    assert config.read_text(encoding="utf-8") == "curvature_tol=2.0\n"


def test_restore_config_removes_new_file(tmp_path: Path) -> None:
    config = tmp_path / "Ortho4XP.cfg"
    original = patch_config_values(config, {"mesh_zl": 18})
    assert config.exists()
    restore_config(config, original)
    assert not config.exists()


def test_build_command_variants(tmp_path: Path) -> None:
    script = tmp_path / "Ortho4XP_v140.py"
    script.write_text("pass", encoding="utf-8")
    output_dir = tmp_path / "out"

    cmd = build_command(script, "+47+008", output_dir, extra_args=["--foo"], python_exe="py")
    assert cmd[:3] == ["py", str(script), "--foo"]
    assert "--output" in cmd

    cmd = build_command(script, "+47+008", output_dir, include_output=False)
    assert "--output" not in cmd


def test_default_scenery_paths() -> None:
    root = Path("XPlane")
    assert default_scenery_root(root).as_posix().endswith("XPlane/Custom Scenery")
    assert tile_scenery_dir(root, "+47+008").as_posix().endswith("XPlane/zOrtho4XP_+47+008")




def test_ortho4xp_version_parsing() -> None:
    assert ortho4xp_version(Path("Ortho4XP_v1.py")) == "1.0"
    assert ortho4xp_version(Path("Ortho4XP_v140.py")) == "1.40"
    assert ortho4xp_version(Path("Ortho4XP_v13.py")) == "1.3"
    assert ortho4xp_version(Path("Ortho4XP_v130.py")) == "1.30"
    assert ortho4xp_version(Path("Ortho4XP.py")) is None


def test_parse_python_version() -> None:
    assert parse_python_version("Python 3.13.3") == (3, 13, 3)
    assert parse_python_version("Python 3.10") == (3, 10, 0)
    assert parse_python_version("nope") is None


def test_resolve_python_executable_default() -> None:
    assert resolve_python_executable(None) == sys.executable


def test_resolve_python_executable_missing(monkeypatch, tmp_path: Path) -> None:
    python_exe = tmp_path / "missing-python"
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.shutil.which",
        lambda *_: None,
    )
    assert resolve_python_executable(str(python_exe)) is None


def test_resolve_python_executable_existing(tmp_path: Path) -> None:
    python_exe = tmp_path / "python"
    python_exe.write_text("bin", encoding="utf-8")
    assert resolve_python_executable(str(python_exe)) == str(python_exe)


def test_probe_python_runtime_default() -> None:
    resolved, version, error = probe_python_runtime(None)
    assert resolved == sys.executable
    assert version == sys.version_info[:3]
    assert error is None


def test_probe_python_runtime_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.resolve_python_executable",
        lambda *_: None,
    )
    resolved, version, error = probe_python_runtime("missing")
    assert resolved is None
    assert version is None
    assert "not found" in (error or "")


def test_probe_python_runtime_oserror(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.resolve_python_executable",
        lambda *_: "fakepython",
    )

    def boom(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr("dem2dsf.tools.ortho4xp.subprocess.run", boom)
    resolved, version, error = probe_python_runtime("fakepython")
    assert resolved == "fakepython"
    assert version is None
    assert "boom" in (error or "")


def test_probe_python_runtime_empty_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.resolve_python_executable",
        lambda *_: "fakepython",
    )
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="", stderr=""),
    )
    resolved, version, error = probe_python_runtime("fakepython")
    assert resolved == "fakepython"
    assert version is None
    assert "no output" in (error or "")


def test_probe_python_runtime_unparseable(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.resolve_python_executable",
        lambda *_: "fakepython",
    )
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="", stderr="??"),
    )
    resolved, version, error = probe_python_runtime("fakepython")
    assert resolved == "fakepython"
    assert version is None
    assert "Unrecognized" in (error or "")


def test_probe_python_runtime_parses_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.resolve_python_executable",
        lambda *_: "fakepython",
    )
    monkeypatch.setattr(
        "dem2dsf.tools.ortho4xp.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="Python 3.11.5", stderr=""),
    )
    resolved, version, error = probe_python_runtime("fakepython")
    assert resolved == "fakepython"
    assert version == (3, 11, 5)
    assert error is None
