"""Build wheel and sdist release artifacts."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _has_build_module() -> bool:
    """Return True if the build module is available."""
    result = subprocess.run(
        [sys.executable, "-m", "build", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def main() -> int:
    """Build release artifacts using python -m build."""
    if not _has_build_module():
        print("Missing build module. Install with: python -m pip install build")
        return 2
    if not shutil.which("python") and sys.executable is None:
        print("Python executable not found.")
        return 2
    result = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--wheel"],
        check=False,
    )
    if result.returncode != 0:
        print("Release build failed.")
        return result.returncode
    print(f"Release artifacts available in {Path('dist').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
