from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

from dem2dsf.doctor import run_doctor
from dem2dsf.tools import config as tool_config
from dem2dsf.tools import installer
from dem2dsf.tools.dsftool import roundtrip_dsf, run_dsftool
from dem2dsf.tools.ortho4xp import TARGET_ORTHO4XP_VERSION, ortho4xp_version
from dem2dsf.xp12 import enrich_dsf_rasters
from dem2dsf.xplane_paths import parse_tile
from tests.utils import with_src_env, write_raster

pytestmark = pytest.mark.integration

ORTHO4XP_SOURCE_URL = "https://github.com/oscarpilote/Ortho4XP"
XPTOOLS_SOURCE_URL = "https://developer.x-plane.com/tools/xptools/"
RUN_ORTHO_BUILD_ENV = "DEM2DSF_RUN_ORTHO4XP_BUILD"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _tool_search_dirs(repo_root: Path) -> list[Path]:
    install_root = repo_root / "tools"
    return [
        install_root / "xptools",
        install_root / "ortho4xp",
        Path.home() / "Ortho4XP",
        Path.home() / "XPTools",
    ]


def _resolve_tool_path(
    name: str,
    *,
    tool_paths: dict[str, Path],
    search_dirs: list[Path],
    finder,
) -> tuple[Path | None, bool]:
    configured = tool_paths.get(name)
    if configured and configured.exists():
        return configured, True
    return finder(search_dirs), False


def _default_xplane_roots() -> list[Path]:
    if sys.platform.startswith("win"):
        roots = [
            Path("C:/X-Plane 12"),
            Path("C:/X-Plane 11"),
            Path("C:/X-Plane 10"),
        ]
    elif sys.platform == "darwin":
        roots = [
            Path("/Applications/X-Plane 12"),
            Path("/Applications/X-Plane 11"),
            Path("/Applications/X-Plane 10"),
        ]
    else:
        roots = [
            Path.home() / "X-Plane 12",
            Path.home() / "X-Plane 11",
            Path.home() / "X-Plane 10",
        ]
    explicit_root = os.environ.get("DEM2DSF_XPLANE_ROOT")
    if explicit_root:
        roots.append(Path(explicit_root).expanduser())
    return roots


def _find_first_dsf(root: Path) -> Path | None:
    earth_nav = root / "Earth nav data"
    if not earth_nav.exists():
        return None
    for dsf_path in earth_nav.rglob("*.dsf"):
        return dsf_path
    return None


def _resolve_global_dsf() -> Path | None:
    explicit = os.environ.get("DEM2DSF_DSF_PATH")
    if explicit:
        explicit_path = Path(explicit).expanduser()
        if explicit_path.exists():
            return explicit_path
    for root in _default_xplane_roots():
        if not root.exists():
            continue
        for scenery in (
            root / "Global Scenery" / "X-Plane 12 Global Scenery",
            root / "Global Scenery" / "X-Plane 11 Global Scenery",
            root / "Global Scenery" / "X-Plane 10 Global Scenery",
        ):
            if not scenery.exists():
                continue
            dsf_path = _find_first_dsf(scenery)
            if dsf_path:
                return dsf_path
    return None


def test_integration_ortho4xp_runner_dry_run(tmp_path: Path) -> None:
    repo_root = _repo_root()
    tool_paths = tool_config.load_tool_paths()
    search_dirs = _tool_search_dirs(repo_root)
    script_path, configured = _resolve_tool_path(
        "ortho4xp",
        tool_paths=tool_paths,
        search_dirs=search_dirs,
        finder=installer.find_ortho4xp,
    )
    if not script_path:
        pytest.skip(f"Ortho4XP not found (source: {ORTHO4XP_SOURCE_URL}).")
    if configured:
        version = ortho4xp_version(script_path)
        if version and not version.startswith("1.4"):
            warnings.warn(
                f"Ortho4XP {version} detected; dem2dsf targets {TARGET_ORTHO4XP_VERSION}.",
                RuntimeWarning,
                stacklevel=2,
            )

    runner = repo_root / "scripts" / "ortho4xp_runner.py"
    if not runner.exists():
        pytest.skip("scripts/ortho4xp_runner.py not found.")
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("synthetic", encoding="utf-8")
    output_dir = tmp_path / "build"

    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--tile",
            "+47+008",
            "--dem",
            str(dem_path),
            "--output",
            str(output_dir),
            "--ortho-root",
            str(script_path.parent),
            "--skip-dem-stage",
            "--dry-run",
        ],
        env=with_src_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert str(script_path) in output
    for line in output.splitlines():
        if "Dry run command:" in line:
            cmd_line = line.split("Dry run command:", 1)[1].strip()
            tokens = shlex.split(cmd_line, posix=False)
            lat, lon = parse_tile("+47+008")
            assert "--tile" not in tokens
            assert str(lat) in tokens
            assert str(lon) in tokens
            break
    else:
        raise AssertionError("Dry run command not found in output.")


def test_integration_ortho4xp_entrypoint_uses_supported_args(tmp_path: Path) -> None:
    repo_root = _repo_root()
    tool_paths = tool_config.load_tool_paths()
    search_dirs = _tool_search_dirs(repo_root)
    script_path, _ = _resolve_tool_path(
        "ortho4xp",
        tool_paths=tool_paths,
        search_dirs=search_dirs,
        finder=installer.find_ortho4xp,
    )
    if not script_path:
        pytest.skip(f"Ortho4XP not found (source: {ORTHO4XP_SOURCE_URL}).")
    runner = repo_root / "scripts" / "ortho4xp_runner.py"
    if not runner.exists():
        pytest.skip("scripts/ortho4xp_runner.py not found.")
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("synthetic", encoding="utf-8")
    output_dir = tmp_path / "build"

    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--tile",
            "+47+008",
            "--dem",
            str(dem_path),
            "--output",
            str(output_dir),
            "--ortho-root",
            str(script_path.parent),
            "--dry-run",
            "--batch",
            "--pass-output",
        ],
        env=with_src_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    for line in output.splitlines():
        if "Dry run command:" in line:
            cmd_line = line.split("Dry run command:", 1)[1].strip()
            tokens = shlex.split(cmd_line, posix=False)
            assert "--batch" not in tokens
            assert "--output" not in tokens
            break
    else:
        raise AssertionError("Dry run command not found in output.")


def test_integration_ortho4xp_build_smoke(tmp_path: Path) -> None:
    if not os.environ.get(RUN_ORTHO_BUILD_ENV):
        pytest.skip(f"Set {RUN_ORTHO_BUILD_ENV}=1 to enable Ortho4XP build smoke test.")
    repo_root = _repo_root()
    tool_paths = tool_config.load_tool_paths()
    search_dirs = _tool_search_dirs(repo_root)
    script_path, _ = _resolve_tool_path(
        "ortho4xp",
        tool_paths=tool_paths,
        search_dirs=search_dirs,
        finder=installer.find_ortho4xp,
    )
    if not script_path:
        pytest.skip(f"Ortho4XP not found (source: {ORTHO4XP_SOURCE_URL}).")
    runner = repo_root / "scripts" / "ortho4xp_runner.py"
    if not runner.exists():
        pytest.skip("scripts/ortho4xp_runner.py not found.")

    dem_path = tmp_path / "dem.tif"
    write_raster(
        dem_path,
        data=np.array([[100.0, 101.0], [102.0, 103.0]], dtype="float32"),
        bounds=(8.0, 47.0, 9.0, 48.0),
        nodata=-9999.0,
    )
    output_dir = tmp_path / "build"

    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--tile",
            "+47+008",
            "--dem",
            str(dem_path),
            "--output",
            str(output_dir),
            "--ortho-root",
            str(script_path.parent),
            "--batch",
            "--autoortho",
        ],
        env=with_src_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert (output_dir / "Earth nav data").exists()


def test_integration_dsftool_roundtrip(tmp_path: Path) -> None:
    repo_root = _repo_root()
    tool_paths = tool_config.load_tool_paths()
    search_dirs = _tool_search_dirs(repo_root)
    dsftool, _ = _resolve_tool_path(
        "dsftool",
        tool_paths=tool_paths,
        search_dirs=search_dirs,
        finder=installer.find_dsftool,
    )
    if not dsftool:
        pytest.skip(f"DSFTool not found (source: {XPTOOLS_SOURCE_URL}).")

    dsf_path = _resolve_global_dsf()
    if dsf_path:
        roundtrip_dsf([str(dsftool)], dsf_path, tmp_path)
        assert (tmp_path / f"{dsf_path.stem}.txt").exists()
    else:
        result = run_dsftool([str(dsftool)], ["--help"])
        assert result.returncode == 0, (
            f"DSFTool --help failed (code {result.returncode}).\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def test_integration_xp12_enrichment(tmp_path: Path) -> None:
    repo_root = _repo_root()
    tool_paths = tool_config.load_tool_paths()
    search_dirs = _tool_search_dirs(repo_root)
    dsftool, _ = _resolve_tool_path(
        "dsftool",
        tool_paths=tool_paths,
        search_dirs=search_dirs,
        finder=installer.find_dsftool,
    )
    if not dsftool:
        pytest.skip(f"DSFTool not found (source: {XPTOOLS_SOURCE_URL}).")

    global_dsf = _resolve_global_dsf()
    if not global_dsf:
        pytest.skip("Global scenery DSF not found for XP12 enrichment test.")

    target_dsf = tmp_path / global_dsf.name
    shutil.copy(global_dsf, target_dsf)

    result = enrich_dsf_rasters([str(dsftool)], target_dsf, global_dsf, tmp_path / "xp12")
    assert result.status in {"enriched", "no-op"}


def test_integration_doctor_reports_tools() -> None:
    repo_root = _repo_root()
    tool_paths = tool_config.load_tool_paths()
    search_dirs = _tool_search_dirs(repo_root)
    ortho_script, _ = _resolve_tool_path(
        "ortho4xp",
        tool_paths=tool_paths,
        search_dirs=search_dirs,
        finder=installer.find_ortho4xp,
    )
    dsftool, _ = _resolve_tool_path(
        "dsftool",
        tool_paths=tool_paths,
        search_dirs=search_dirs,
        finder=installer.find_dsftool,
    )
    if not ortho_script or not dsftool:
        pytest.skip("Ortho4XP or XPTools not installed for doctor integration.")
    runner = repo_root / "scripts" / "ortho4xp_runner.py"
    if not runner.exists():
        pytest.skip("scripts/ortho4xp_runner.py not found.")
    results = run_doctor(
        ortho_runner=[
            sys.executable,
            str(runner),
            "--ortho-root",
            str(ortho_script.parent),
        ],
        dsftool_path=[str(dsftool)],
    )
    status_map = {result.name: result.status for result in results}
    assert status_map["ortho4xp_version"] in ("ok", "warn")
    assert status_map["ortho4xp_python"] in ("ok", "warn")
    assert status_map["dsftool"] in ("ok", "warn")
