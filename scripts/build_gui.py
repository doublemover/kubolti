"""Build a standalone GUI bundle using PyInstaller."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_ICON = Path("assets") / "ballcow_icon.png"


def _default_repo_root() -> Path:
    """Return the repository root path."""
    return Path(__file__).resolve().parents[1]


def _default_entry(root: Path) -> Path:
    """Return the default GUI entrypoint path."""
    return root / "src" / "dem2dsf" / "gui.py"


def _default_runner(root: Path) -> Path:
    """Return the default Ortho4XP runner path."""
    return root / "scripts" / "ortho4xp_runner.py"


def _supports_png_icon() -> bool:
    """Return True if PNG icons can be converted for the current platform."""
    try:
        import PIL.Image  # noqa: F401
    except ImportError:
        return False
    return True


def _icon_allowed(path: Path) -> bool:
    """Return True if the icon path should be passed to PyInstaller."""
    suffix = path.suffix.lower()
    if sys.platform.startswith("win"):
        if suffix == ".ico":
            return True
        if suffix == ".png" and _supports_png_icon():
            return True
        return False
    if sys.platform == "darwin":
        return suffix in {".icns", ".png"}
    return suffix in {".png", ".ico"}


def _data_separator() -> str:
    """Return the PyInstaller add-data separator for the platform."""
    return ";" if sys.platform.startswith("win") else ":"


def _has_pyinstaller() -> bool:
    """Return True if PyInstaller is available."""
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for GUI packaging."""
    windowed_default = sys.platform.startswith("win") or sys.platform == "darwin"
    parser = argparse.ArgumentParser(description="Build a standalone GUI bundle with PyInstaller.")
    parser.add_argument("--name", default="dem2dsf-gui", help="Bundle name.")
    parser.add_argument(
        "--output-dir",
        default=str(Path("dist") / "gui"),
        help="Output directory for build artifacts.",
    )
    parser.add_argument(
        "--entry",
        help="GUI entrypoint (defaults to src/dem2dsf/gui.py).",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Build a single-file binary (default).",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build a one-directory bundle.",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Hide the console window (default on Windows/macOS).",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Force a console window.",
    )
    parser.add_argument(
        "--icon",
        help="Optional icon file (defaults to assets/ballcow_icon.png).",
    )
    parser.add_argument("--no-icon", action="store_true", help="Skip icon bundling.")
    parser.add_argument(
        "--no-runner",
        action="store_true",
        help="Skip bundling scripts/ortho4xp_runner.py.",
    )
    parser.add_argument(
        "--runner-path",
        help="Override the Ortho4XP runner path to bundle.",
    )
    parser.add_argument("--clean", action="store_true", help="Clean PyInstaller cache.")
    parser.add_argument("--noconfirm", action="store_true", help="Overwrite existing bundles.")
    parser.add_argument("--dry-run", action="store_true", help="Print the PyInstaller command.")
    args = parser.parse_args(argv)

    if args.onefile and args.onedir:
        parser.error("Pick --onefile or --onedir, not both.")
    if not args.onefile and not args.onedir:
        args.onefile = True
    if args.windowed and args.console:
        parser.error("Pick --windowed or --console, not both.")
    if not args.windowed and not args.console:
        args.windowed = windowed_default
    if not args.icon and not args.no_icon:
        default_icon = _default_repo_root() / DEFAULT_ICON
        if default_icon.exists():
            args.icon = str(default_icon)
    args.include_runner = not args.no_runner
    return args


def _build_command(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """Build the PyInstaller command and any warnings."""
    root = _default_repo_root()
    entry = Path(args.entry) if args.entry else _default_entry(root)
    dist_path = Path(args.output_dir)
    work_path = dist_path / "build"
    spec_path = dist_path / "spec"
    warnings: list[str] = []

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        args.name,
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_path),
        "--specpath",
        str(spec_path),
        "--paths",
        str(root / "src"),
    ]
    cmd.append("--onefile" if args.onefile else "--onedir")
    cmd.append("--windowed" if args.windowed else "--console")
    if args.icon:
        icon_path = Path(args.icon)
        if icon_path.exists() and _icon_allowed(icon_path):
            cmd.extend(["--icon", str(icon_path)])
        elif icon_path.exists():
            warnings.append(f"Icon format not supported on this platform: {icon_path}")
        else:
            warnings.append(f"Icon file not found: {icon_path}")
    if args.clean:
        cmd.append("--clean")
    if args.noconfirm:
        cmd.append("--noconfirm")
    if args.include_runner:
        runner_path = Path(args.runner_path) if args.runner_path else _default_runner(root)
        if runner_path.exists():
            cmd.extend(["--add-data", f"{runner_path}{_data_separator()}scripts"])
        else:
            warnings.append(f"Runner script not found: {runner_path}")
    cmd.append(str(entry))
    return cmd, warnings


def main(argv: list[str] | None = None) -> int:
    """Build the GUI bundle and return an exit code."""
    args = _parse_args(argv)
    if not _has_pyinstaller():
        print("Missing PyInstaller. Install with: python -m pip install pyinstaller")
        return 2
    if sys.executable is None and not shutil.which("python"):
        print("Python executable not found.")
        return 2

    root = _default_repo_root()
    entry = Path(args.entry) if args.entry else _default_entry(root)
    if not entry.exists():
        print(f"GUI entrypoint not found: {entry}")
        return 2

    command, warnings = _build_command(args)
    for warning in warnings:
        print(f"Warning: {warning}")
    if args.dry_run:
        print(" ".join(command))
        return 0

    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print("GUI build failed.")
        return result.returncode
    print(f"GUI bundle available in {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
