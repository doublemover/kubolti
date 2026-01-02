from __future__ import annotations

import os
import sys
from pathlib import Path


def _venv_python(root: Path) -> Path | None:
    if os.name == "nt":
        candidate = root / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = root / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else None


def _reexec_in_venv() -> None:
    if os.environ.get("DEM2DSF_SKIP_VENV_REEXEC") == "1":
        return
    root = Path(__file__).resolve().parents[1]
    venv_python = _venv_python(root)
    if not venv_python:
        return
    if Path(sys.executable).resolve() == venv_python.resolve():
        return
    os.environ["DEM2DSF_SKIP_VENV_REEXEC"] = "1"
    os.execv(
        str(venv_python),
        [str(venv_python), "-m", "pytest", *sys.argv[1:]],
    )


_reexec_in_venv()

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest  # noqa: E402

from dem2dsf.tools import config as tool_config  # noqa: E402


def pytest_collection_modifyitems(config, items) -> None:
    """Skip integration tests unless explicitly selected via -m integration."""
    markexpr = config.option.markexpr or ""
    if "integration" in markexpr:
        return
    skip_integration = pytest.mark.skip(reason="integration tests run only with -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def _isolate_tool_paths(monkeypatch, tmp_path) -> None:
    """Prevent local tool configs from bleeding into tests."""
    monkeypatch.setenv(tool_config.ENV_TOOL_PATHS, str(tmp_path / "missing_tool_paths.json"))
