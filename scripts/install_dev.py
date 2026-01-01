"""Bootstrap a local virtual environment with dev dependencies."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

MIN_PYTHON = (3, 13)


def _venv_python(venv_dir: Path) -> Path:
    """Return the platform-specific venv python path."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def main() -> int:
    """Create a .venv and install dev dependencies."""
    if sys.version_info < MIN_PYTHON:
        print("Python 3.13+ is required.")
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    venv_dir = repo_root / ".venv"

    if not venv_dir.exists():
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(venv_dir)

    python = _venv_python(venv_dir)
    if not python.exists():
        print(f"Virtualenv python not found at {python}")
        return 1

    subprocess.check_call([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(python), "-m", "pip", "install", "--upgrade", "setuptools", "wheel"])
    subprocess.check_call([str(python), "-m", "pip", "install", "-e", f"{repo_root}[dev]"])

    print("Installed dev dependencies into .venv.")
    print("Activate the environment and run: pytest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
