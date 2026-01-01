"""Install and discover external tools for dem2dsf."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dem2dsf.tools.config import ENV_TOOL_PATHS
from dem2dsf.tools.installer import (
    InstallResult,
    ensure_sevenzip,
    ensure_tool_config,
    find_dsftool,
    find_ddstool,
    find_ortho4xp,
    install_from_archive,
    install_from_url,
    install_ortho4xp,
    is_url,
)

DEFAULT_ORTHO4XP_URL = "https://github.com/oscarpilote/Ortho4XP.git"
DEFAULT_XPTOOLS_URLS = {
    "win32": "https://files.x-plane.com/public/xptools/xptools_win_24-5.zip",
    "darwin": "https://files.x-plane.com/public/xptools/xptools_mac_24-5.zip",
    "linux": "https://files.x-plane.com/public/xptools/xptools_lin_24-5.zip",
}


def _default_xptools_url() -> str | None:
    """Return the default XPTools URL for this platform."""
    if sys.platform.startswith("win"):
        return DEFAULT_XPTOOLS_URLS["win32"]
    if sys.platform == "darwin":
        return DEFAULT_XPTOOLS_URLS["darwin"]
    if sys.platform.startswith("linux"):
        return DEFAULT_XPTOOLS_URLS["linux"]
    return None


def _prompt(prompt: str) -> str:
    """Prompt for input, returning an empty string on EOF."""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def _run_install_command(command: list[str]) -> bool:
    """Run a package manager command and return success."""
    try:
        result = subprocess.run(command, check=False)
    except OSError:
        return False
    return result.returncode == 0


def _choco_install_command() -> list[str]:
    return [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Set-ExecutionPolicy Bypass -Scope Process -Force; "
        "[System.Net.ServicePointManager]::SecurityProtocol = "
        "[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
        "iex ((New-Object System.Net.WebClient).DownloadString("
        "'https://community.chocolatey.org/install.ps1'))",
    ]


def _ensure_choco(interactive: bool) -> bool:
    if shutil.which("choco"):
        return True
    if (
        not interactive
        or _prompt(
            "Install Chocolatey via official install script? "
            "(Requires administrator privileges/UAC.) [y/N]: "
        ).lower()
        == "y"
    ):
        return _run_install_command(_choco_install_command())
    return False


def _install_7zip(interactive: bool) -> bool:
    """Attempt to install 7-Zip via common package managers."""
    if os.name == "nt":
        if shutil.which("winget"):
            if (
                not interactive
                or _prompt(
                    "Install 7-Zip via winget? "
                    "(Requires administrator privileges/UAC.) [y/N]: "
                ).lower()
                == "y"
            ):
                return _run_install_command(
                    ["winget", "install", "-e", "--id", "7zip.7zip"]
                )
        if _ensure_choco(interactive):
            if (
                not interactive
                or _prompt(
                    "Install 7-Zip via choco? "
                    "(Requires administrator privileges/UAC.) [y/N]: "
                ).lower()
                == "y"
            ):
                return _run_install_command(["choco", "install", "7zip", "-y"])
    elif sys.platform == "darwin" and shutil.which("brew"):
        if not interactive or _prompt("Install 7-Zip via brew? [y/N]: ").lower() == "y":
            return _run_install_command(["brew", "install", "p7zip"])
    else:
        if shutil.which("apt-get"):
            if not interactive or _prompt("Install 7-Zip via apt-get? [y/N]: ").lower() == "y":
                return _run_install_command(
                    ["sudo", "apt-get", "install", "-y", "p7zip-full"]
                )
        if shutil.which("dnf"):
            if not interactive or _prompt("Install 7-Zip via dnf? [y/N]: ").lower() == "y":
                return _run_install_command(["sudo", "dnf", "install", "-y", "p7zip"])
        if shutil.which("pacman"):
            if not interactive or _prompt("Install 7-Zip via pacman? [y/N]: ").lower() == "y":
                return _run_install_command(["sudo", "pacman", "-S", "--noconfirm", "p7zip"])
    return False


def _resolve_archive(path_value: str) -> Path | None:
    """Resolve a local archive path if it exists."""
    if not path_value:
        return None
    candidate = Path(path_value).expanduser()
    if candidate.exists():
        return candidate
    return None


def _resolve_url(value: str) -> str | None:
    """Return the value if it is a URL."""
    return value if value and is_url(value) else None


def _resolve_existing_dir(value: str) -> Path | None:
    """Resolve a directory path if it exists."""
    if not value:
        return None
    candidate = Path(value).expanduser()
    return candidate if candidate.exists() else None


def _ensure_dsftool(
    search_dirs: list[Path],
    *,
    url: str | None,
    archive: Path | None,
    install_root: Path,
    interactive: bool,
    skip_install: bool,
) -> InstallResult:
    """Locate or install DSFTool from URL or archive."""
    found = find_dsftool(search_dirs)
    if found:
        return InstallResult("dsftool", "ok", found, "found")
    if skip_install:
        return InstallResult("dsftool", "missing", None, "not found")
    install_dir = install_root / "xptools"
    if url:
        try:
            found = install_from_url(
                url,
                install_dir,
                executable_names=("DSFTool.exe", "DSFTool", "dsftool"),
            )
            return InstallResult("dsftool", "ok", found, f"downloaded from {url}")
        except Exception as exc:
            return InstallResult("dsftool", "error", None, str(exc))
    if archive:
        try:
            found = install_from_archive(
                archive,
                install_dir,
                executable_names=("DSFTool.exe", "DSFTool", "dsftool"),
            )
            return InstallResult("dsftool", "ok", found, f"installed from {archive}")
        except Exception as exc:
            return InstallResult("dsftool", "error", None, str(exc))
    if interactive:
        response = _prompt("Path or URL to XPTools archive (blank to skip): ")
        if is_url(response):
            return _ensure_dsftool(
                search_dirs,
                url=response,
                archive=None,
                install_root=install_root,
                interactive=False,
                skip_install=False,
            )
        archive_path = _resolve_archive(response)
        if archive_path:
            return _ensure_dsftool(
                search_dirs,
                url=None,
                archive=archive_path,
                install_root=install_root,
                interactive=False,
                skip_install=False,
            )
    return InstallResult("dsftool", "missing", None, "not installed")

def _ensure_ortho4xp(
    search_dirs: list[Path],
    *,
    url: str,
    install_root: Path,
    interactive: bool,
    skip_install: bool,
) -> InstallResult:
    """Locate or install Ortho4XP via repo or archive."""
    found = find_ortho4xp(search_dirs)
    if found:
        return InstallResult("ortho4xp", "ok", found, "found")
    if skip_install:
        return InstallResult("ortho4xp", "missing", None, "not found")
    install_dir = install_root / "ortho4xp"
    try:
        found = install_ortho4xp(url, install_dir)
        return InstallResult("ortho4xp", "ok", found, f"installed from {url}")
    except Exception as exc:
        if interactive:
            response = _prompt("Ortho4XP root path (blank to skip): ")
            existing = _resolve_existing_dir(response)
            if existing:
                found = find_ortho4xp([existing])
                if found:
                    return InstallResult(
                        "ortho4xp", "ok", found, f"using {existing}"
                    )
        return InstallResult("ortho4xp", "error", None, str(exc))


def main() -> int:
    """CLI entrypoint for installing external tools."""
    parser = argparse.ArgumentParser(description="Install external tooling for dem2dsf.")
    parser.add_argument(
        "--root",
        help="Install root for downloaded tools (default: <repo>/tools)",
    )
    parser.add_argument(
        "--tools",
        default="7zip,ortho4xp,dsftool",
        help="Comma-separated tool list to install.",
    )
    parser.add_argument(
        "--ortho4xp-url",
        default=DEFAULT_ORTHO4XP_URL,
        help="Ortho4XP git repo or archive URL.",
    )
    parser.add_argument(
        "--xptools-url",
        default=_default_xptools_url(),
        help="XPTools archive URL (DSFTool).",
    )
    parser.add_argument("--xptools-archive", help="Local XPTools archive path.")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable prompts.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only report tool status, do not attempt installs.",
    )
    parser.add_argument(
        "--write-config",
        action="store_true",
        help="Write tools/tool_paths.json with discovered paths.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    install_root = Path(args.root) if args.root else repo_root / "tools"

    tools = {tool.strip().lower() for tool in args.tools.split(",") if tool.strip()}
    interactive = not args.non_interactive
    archive_path = _resolve_archive(args.xptools_archive or "")
    url_value = args.xptools_url or ""

    print(f"Install root: {install_root}")
    print(f"Tools requested: {', '.join(sorted(tools)) or 'none'}")
    print(f"Mode: downloads only, {'interactive' if interactive else 'non-interactive'}")
    if args.check_only:
        print("Check-only: will not install missing tools.")
    if url_value and not is_url(url_value):
        print(f"Note: --xptools-url ignored (not a URL): {url_value}")
    if args.xptools_archive and not archive_path:
        print(f"Note: --xptools-archive not found: {args.xptools_archive}")

    search_dirs = [
        install_root / "xptools",
        install_root / "ortho4xp",
        Path.home() / "Ortho4XP",
        Path.home() / "XPTools",
    ]

    results: list[InstallResult] = []
    tool_paths: dict[str, Path] = {}

    if "7zip" in tools or "7z" in tools:
        sevenzip = ensure_sevenzip()
        results.append(sevenzip)
        if sevenzip.status != "ok" and not args.check_only:
            _install_7zip(interactive)
            sevenzip = ensure_sevenzip()
        if sevenzip.path:
            tool_paths["7zip"] = sevenzip.path

    if "ortho4xp" in tools:
        results.append(
            _ensure_ortho4xp(
                search_dirs,
                url=args.ortho4xp_url,
                install_root=install_root,
                interactive=interactive,
                skip_install=args.check_only,
            )
        )
        if results[-1].path:
            tool_paths["ortho4xp"] = results[-1].path

    if "dsftool" in tools or "xptools" in tools:
        dsftool_result = _ensure_dsftool(
            search_dirs,
            url=_resolve_url(url_value),
            archive=archive_path,
            install_root=install_root,
            interactive=interactive,
            skip_install=args.check_only,
        )
        results.append(dsftool_result)
        if dsftool_result.path:
            tool_paths["dsftool"] = dsftool_result.path
        if "ddstool" in tools or "xptools" in tools or "dsftool" in tools:
            ddstool_path = find_ddstool(search_dirs)
            if ddstool_path:
                results.append(
                    InstallResult("ddstool", "ok", ddstool_path, "found")
                )
                tool_paths["ddstool"] = ddstool_path
            else:
                results.append(
                    InstallResult("ddstool", "missing", None, "not found")
                )

    for result in results:
        path = str(result.path) if result.path else "-"
        print(f"{result.name}: {result.status} ({path}) -> {result.detail}")

    if args.write_config and tool_paths:
        config_path = ensure_tool_config(install_root / "tool_paths.json", tool_paths)
        print(f"Wrote tool config to {config_path}")
        print(f"Tip: set {ENV_TOOL_PATHS} to this path for auto-detection.")
    elif args.write_config:
        print("No tool paths found; config not written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
