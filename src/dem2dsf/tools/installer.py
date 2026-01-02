"""Installer helpers for external tools and archives."""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import struct
import subprocess
import sys
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


_MACHO_MAGICS = {
    b"\xFE\xED\xFA\xCE",
    b"\xCE\xFA\xED\xFE",
    b"\xFE\xED\xFA\xCF",
    b"\xCF\xFA\xED\xFE",
}
_FAT_MAGICS = {b"\xCA\xFE\xBA\xBE", b"\xBE\xBA\xFE\xCA"}
_CPU_TYPE_X86 = 7
_CPU_TYPE_ARM = 12
_CPU_ARCH_ABI64 = 0x01000000
_CPU_TYPE_X86_64 = _CPU_TYPE_X86 | _CPU_ARCH_ABI64
_CPU_TYPE_ARM64 = _CPU_TYPE_ARM | _CPU_ARCH_ABI64


def _darwin_cpu_matches(cputype: int) -> bool:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return cputype == _CPU_TYPE_ARM64
    if machine in {"x86_64", "amd64"}:
        return cputype == _CPU_TYPE_X86_64
    return True


def _darwin_is_compatible_macho(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            header = handle.read(8)
            if len(header) < 8:
                return False
            magic = header[:4]
            if magic in _FAT_MAGICS:
                endian = ">" if magic == b"\xCA\xFE\xBA\xBE" else "<"
                nfat_arch = struct.unpack(f"{endian}I", header[4:8])[0]
                table_size = 8 + nfat_arch * 20
                data = header + handle.read(max(0, table_size - len(header)))
                if len(data) < table_size:
                    return False
                offset = 8
                for _ in range(nfat_arch):
                    cputype = struct.unpack(f"{endian}I", data[offset : offset + 4])[0]
                    if _darwin_cpu_matches(cputype):
                        return True
                    offset += 20
                return False
            if magic in _MACHO_MAGICS:
                cputype_le = struct.unpack("<I", header[4:8])[0]
                cputype_be = struct.unpack(">I", header[4:8])[0]
                return _darwin_cpu_matches(cputype_le) or _darwin_cpu_matches(cputype_be)
            return False
    except OSError:
        return False


def is_executable_file(path: Path) -> bool:
    """Return True if the path looks like a runnable tool binary/script."""
    if not path.is_file():
        return False
    if os.name == "nt":
        return path.suffix.lower() in {".exe", ".bat", ".cmd"}
    try:
        with path.open("rb") as handle:
            header = handle.read(8)
    except OSError:
        return False
    if header.startswith(b"#!"):
        return True
    if sys.platform == "darwin":
        return _darwin_is_compatible_macho(path)
    return header[:4] == b"\x7fELF"


def ensure_executable(path: Path) -> None:
    """Mark a tool binary as executable on POSIX systems."""
    if os.name == "nt":
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _find_executable(names: Iterable[str], search_dirs: Iterable[Path]) -> Path | None:
    """Search PATH and directories for an executable."""
    for name in names:
        which = shutil.which(name)
        if which:
            return Path(which)
    for root in search_dirs:
        for name in names:
            candidate = root / name
            if is_executable_file(candidate):
                return candidate
    return None


def _find_in_tree(root: Path, names: Iterable[str]) -> Path | None:
    """Search a directory tree for matching file names."""
    for name in names:
        for candidate in root.rglob(name):
            if is_executable_file(candidate):
                return candidate
    return None


def find_dsftool(search_dirs: Iterable[Path]) -> Path | None:
    """Locate DSFTool in PATH or search directories."""
    if os.name == "nt":
        names = ("DSFTool.exe", "DSFTool", "dsftool")
    else:
        names = ("DSFTool", "dsftool")
    found = _find_executable(names, search_dirs)
    if found:
        return found
    for root in search_dirs:
        found = _find_in_tree(root, names)
        if found:
            return found
    return None


def find_ddstool(search_dirs: Iterable[Path]) -> Path | None:
    """Locate DDSTool in PATH or search directories."""
    if os.name == "nt":
        names = ("DDSTool.exe", "DDSTool", "ddstool")
    else:
        names = ("DDSTool", "ddstool")
    found = _find_executable(names, search_dirs)
    if found:
        return found
    for root in search_dirs:
        found = _find_in_tree(root, names)
        if found:
            return found
    return None


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
            ensure_executable(found)
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
