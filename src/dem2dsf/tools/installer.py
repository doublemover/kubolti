"""Installer helpers for external tools and archives."""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import urlopen

from dem2dsf.publish import find_sevenzip
from dem2dsf.tools.ortho4xp import Ortho4XPNotFoundError, find_ortho4xp_script


@dataclass(frozen=True)
class InstallResult:
    """Result for a tool install or discovery action."""

    name: str
    status: str
    path: Path | None
    detail: str


def is_url(value: str) -> bool:
    """Return True if the string is a supported URL."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "file"}


def download_file(url: str, destination: Path) -> Path:
    """Download a URL to a local file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url) as response:  # noqa: S310 - controlled URLs only
        destination.write_bytes(response.read())
    return destination


def _safe_extract_path(root: Path, member: Path) -> Path:
    """Ensure an archive member resolves inside the destination root."""
    root_resolved = root.resolve()
    candidate = (root / member).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Archive member escapes target directory.") from exc
    return candidate


def extract_archive(archive_path: Path, destination: Path) -> list[Path]:
    """Extract an archive and return top-level extracted roots."""
    destination.mkdir(parents=True, exist_ok=True)
    extracted_roots: set[Path] = set()
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.namelist():
                if not member:
                    continue
                member_path = Path(member)
                safe_path = _safe_extract_path(destination, member_path)
                if member.endswith("/"):
                    safe_path.mkdir(parents=True, exist_ok=True)
                else:
                    safe_path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, safe_path.open("wb") as target:
                        shutil.copyfileobj(source, target)
                extracted_roots.add(destination / member_path.parts[0])
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                if not member.name:
                    continue
                member_path = Path(member.name)
                safe_path = _safe_extract_path(destination, member_path)
                extracted_roots.add(destination / member_path.parts[0])
            try:
                archive.extractall(destination, filter="data")
            except TypeError:
                archive.extractall(destination)  # noqa: S202 - guarded by validation above
    else:
        raise ValueError(f"Unsupported archive format: {archive_path}")
    return sorted(extracted_roots)


def _find_executable(names: Iterable[str], search_dirs: Iterable[Path]) -> Path | None:
    """Search PATH and directories for an executable."""
    for name in names:
        which = shutil.which(name)
        if which:
            return Path(which)
    for root in search_dirs:
        for name in names:
            candidate = root / name
            if candidate.exists():
                return candidate
    return None


def _find_in_tree(root: Path, names: Iterable[str]) -> Path | None:
    """Search a directory tree for matching file names."""
    for name in names:
        for candidate in root.rglob(name):
            if candidate.is_file():
                return candidate
    return None


def find_dsftool(search_dirs: Iterable[Path]) -> Path | None:
    """Locate DSFTool in PATH or search directories."""
    return _find_executable(
        ("DSFTool.exe", "DSFTool", "dsftool"),
        search_dirs,
    )


def find_ortho4xp(search_dirs: Iterable[Path]) -> Path | None:
    """Locate an Ortho4XP script within search directories."""
    for root in search_dirs:
        try:
            return find_ortho4xp_script(root)
        except Ortho4XPNotFoundError:
            continue
    return None


def install_ortho4xp(repo_url: str, destination: Path) -> Path:
    """Install Ortho4XP from a git repo or archive."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if repo_url.endswith(".git"):
        git = shutil.which("git")
        if not git:
            raise RuntimeError("git is required to clone Ortho4XP.")
        subprocess.check_call([git, "clone", repo_url, str(destination)])
    else:
        archive_path = destination.with_suffix(".zip")
        download_file(repo_url, archive_path)
        roots = extract_archive(archive_path, destination.parent)
        if roots:
            if destination.exists():
                shutil.rmtree(destination)
            roots[0].rename(destination)
    script = find_ortho4xp_script(destination)
    return script


def install_from_archive(
    archive: Path,
    destination: Path,
    *,
    executable_names: Iterable[str],
) -> Path:
    """Extract an archive and locate an executable within it."""
    roots = extract_archive(archive, destination)
    for root in roots or [destination]:
        found = _find_in_tree(root, executable_names)
        if found:
            return found
    raise FileNotFoundError(
        f"Executable not found after extracting {archive} into {destination}"
    )


def install_from_url(
    url: str,
    destination: Path,
    *,
    executable_names: Iterable[str],
) -> Path:
    """Download and install an archive from a URL."""
    archive_path = destination / Path(urlparse(url).path).name
    download_file(url, archive_path)
    return install_from_archive(
        archive_path, destination, executable_names=executable_names
    )


def ensure_sevenzip() -> InstallResult:
    """Check for a usable 7z binary."""
    path = find_sevenzip()
    if path:
        return InstallResult("7zip", "ok", path, "found")
    return InstallResult("7zip", "missing", None, "7z not found in PATH")


def ensure_tool_config(path: Path, tools: dict[str, Path]) -> Path:
    """Write a tool_paths.json file mapping tool names to paths."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: str(tool) for name, tool in tools.items()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
