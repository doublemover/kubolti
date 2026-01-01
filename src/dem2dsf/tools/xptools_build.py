"""Build XPTools from the X-Plane/xptools source repo."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

XPTOOLS_REPO_URL = "https://github.com/X-Plane/xptools.git"
XPTOOLS_LIBS_URL = "https://github.com/X-Plane/xptools_libs.git"
XPTOOLS_MSVC_LIBS_URL = "https://github.com/X-Plane/xptools_msvc_libs.git"
XPTOOLS_TAG = "XPTools_2024_5"
XPTOOLS_COMMIT: str | None = None
DEFAULT_MSVC_TOOLSET = "v143"

ENV_MSBUILD_PATH = "DEM2DSF_MSBUILD_PATH"
ENV_VCVARSALL_PATH = "DEM2DSF_VCVARSALL_PATH"
ENV_MSVC_TOOLSET = "DEM2DSF_MSVC_TOOLSET"
ENV_WINDOWS_SDK_VERSION = "DEM2DSF_WINDOWS_SDK_VERSION"
ENV_XPTOOLS_LIBS_URL = "DEM2DSF_XPTOOLS_LIBS_URL"
ENV_XPTOOLS_MSVC_LIBS_URL = "DEM2DSF_XPTOOLS_MSVC_LIBS_URL"

DEFAULT_MSBUILD_PATHS = [
    Path(
        "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/MSBuild/Current/Bin/MSBuild.exe"
    ),
    Path(
        "C:/Program Files (x86)/Microsoft Visual Studio/2019/BuildTools/MSBuild/Current/Bin/MSBuild.exe"
    ),
]
DEFAULT_VCVARSALL_PATHS = [
    Path(
        "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvarsall.bat"
    ),
    Path(
        "C:/Program Files (x86)/Microsoft Visual Studio/2019/BuildTools/VC/Auxiliary/Build/vcvarsall.bat"
    ),
]


def _parse_sdk_version(value: str) -> tuple[int, ...] | None:
    parts = value.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _detect_windows_sdk_version() -> str | None:
    env_value = os.environ.get(ENV_WINDOWS_SDK_VERSION)
    if env_value:
        return env_value
    kits_root = (
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "Windows Kits"
        / "10"
        / "Lib"
    )
    if not kits_root.exists():
        return None
    versions: list[tuple[tuple[int, ...], str]] = []
    for candidate in kits_root.iterdir():
        if not candidate.is_dir():
            continue
        parsed = _parse_sdk_version(candidate.name)
        if parsed:
            versions.append((parsed, candidate.name))
    if not versions:
        return None
    versions.sort()
    return versions[-1][1]


@dataclass(frozen=True)
class BuiltTool:
    """Result of building a single external tool."""

    name: str
    path: Path


def _run_command(command: list[str], *, cwd: Path | None = None) -> None:
    """Run a command and raise if it fails."""
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}")


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


def _find_msbuild() -> Path | None:
    env_path = os.environ.get(ENV_MSBUILD_PATH)
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate
    for path in DEFAULT_MSBUILD_PATHS:
        if path.exists():
            return path
    base = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    vs_root = base / "Microsoft Visual Studio"
    if vs_root.exists():
        for year in sorted(vs_root.iterdir(), reverse=True):
            if not year.is_dir():
                continue
            for edition in ("BuildTools", "Community", "Professional", "Enterprise"):
                msbuild = (
                    year
                    / edition
                    / "MSBuild"
                    / "Current"
                    / "Bin"
                    / "MSBuild.exe"
                )
                if msbuild.exists():
                    return msbuild
    return None


def _find_vcvarsall(msbuild: Path | None = None) -> Path | None:
    env_path = os.environ.get(ENV_VCVARSALL_PATH)
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate
    if msbuild:
        build_root = msbuild.parents[3]
        candidate = build_root / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
        if candidate.exists():
            return candidate
    for path in DEFAULT_VCVARSALL_PATHS:
        if path.exists():
            return path
    return None


def _detect_msvc_toolset(_msbuild: Path | None) -> str | None:
    env_value = os.environ.get(ENV_MSVC_TOOLSET)
    return env_value if env_value else None


def _install_mac_deps(*, interactive: bool) -> bool:
    if shutil.which("brew"):
        if not interactive or _prompt("Install build deps via brew? [y/N]: ").lower() == "y":
            return _run_install_command(["brew", "install", "git", "make"])
    return False


def _install_linux_deps(*, interactive: bool) -> bool:
    if shutil.which("apt-get"):
        if not interactive or _prompt("Install build deps via apt-get? [y/N]: ").lower() == "y":
            return _run_install_command(
                ["sudo", "apt-get", "install", "-y", "build-essential", "git", "clang"]
            )
    if shutil.which("dnf"):
        if not interactive or _prompt("Install build deps via dnf? [y/N]: ").lower() == "y":
            return _run_install_command(["sudo", "dnf", "install", "-y", "git", "clang", "make"])
    if shutil.which("pacman"):
        if not interactive or _prompt("Install build deps via pacman? [y/N]: ").lower() == "y":
            return _run_install_command(
                ["sudo", "pacman", "-S", "--noconfirm", "--needed", "base-devel", "git", "clang"]
            )
    return False


def ensure_build_deps(*, install: bool, interactive: bool) -> None:
    """Check for build dependencies and optionally install them."""
    if os.name == "nt":
        msbuild = _find_msbuild()
        vcvarsall = _find_vcvarsall(msbuild)
        if msbuild is None or vcvarsall is None:
            raise RuntimeError(
                "MSVC Build Tools not found; install Visual Studio 2017+ Build Tools "
                "(MSBuild + C++ workload) or set "
                f"{ENV_MSBUILD_PATH}/{ENV_VCVARSALL_PATH}."
            )
        if not shutil.which("git"):
            raise RuntimeError("git not found; install git.")
        return

    missing = []
    if not shutil.which("git"):
        missing.append("git")
    if not shutil.which("make"):
        missing.append("make")
    if not shutil.which("clang"):
        missing.append("clang")
    if missing and install:
        if sys.platform == "darwin":
            _install_mac_deps(interactive=interactive)
        else:
            _install_linux_deps(interactive=interactive)
        missing = []
        if not shutil.which("git"):
            missing.append("git")
        if not shutil.which("make"):
            missing.append("make")
        if not shutil.which("clang"):
            missing.append("clang")
    if missing:
        raise RuntimeError(f"Missing build tools: {', '.join(missing)}")


def _ensure_repo(root: Path, *, tag: str, commit: str | None, repo_url: str) -> None:
    if not root.exists():
        _run_command(
            [
                "git",
                "-c",
                "core.longpaths=true",
                "clone",
                "--recurse-submodules",
                repo_url,
                str(root),
            ]
        )
    else:
        status = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain",
                "--untracked-files=no",
                "--ignore-submodules=dirty",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if status.returncode == 0 and status.stdout.strip():
            raise RuntimeError(
                "xptools repo has local changes; remove the source directory "
                f"({root}) or clean the repo before continuing."
            )
    _run_command(["git", "-C", str(root), "config", "core.longpaths", "true"])
    has_tag = (
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", f"refs/tags/{tag}"],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    if not has_tag:
        _run_command(["git", "-C", str(root), "fetch", "--tags"])
    _run_command(["git", "-C", str(root), "checkout", tag])
    gitmodules = root / ".gitmodules"
    has_libs = False
    has_msvc_libs = False
    if gitmodules.exists():
        content = gitmodules.read_text(encoding="utf-8", errors="ignore")
        has_libs = 'submodule "libs"' in content
        has_msvc_libs = 'submodule "msvc_libs"' in content
    if has_libs:
        libs_url = os.environ.get(ENV_XPTOOLS_LIBS_URL, XPTOOLS_LIBS_URL)
        _run_command(
            [
                "git",
                "-C",
                str(root),
                "config",
                "submodule.libs.url",
                libs_url,
            ]
        )
    if has_msvc_libs:
        msvc_libs_url = os.environ.get(ENV_XPTOOLS_MSVC_LIBS_URL, XPTOOLS_MSVC_LIBS_URL)
        _run_command(
            [
                "git",
                "-C",
                str(root),
                "config",
                "submodule.msvc_libs.url",
                msvc_libs_url,
            ]
        )
    if gitmodules.exists():
        _run_command(
            [
                "git",
                "-c",
                "core.longpaths=true",
                "-C",
                str(root),
                "submodule",
                "update",
                "--init",
                "--recursive",
            ]
        )
    if commit:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError("Unable to verify xptools commit.")
        if result.stdout.strip() != commit:
            raise RuntimeError(
                "xptools checkout does not match pinned commit. "
                f"Expected {commit}, got {result.stdout.strip()}."
            )


def _run_make(root: Path, target: str) -> None:
    command = ["make", "CC=clang", "CXX=clang++", "conf=release_opt", target]
    _run_command(command, cwd=root)


def _run_xcodebuild(root: Path, scheme: str) -> None:
    root = root.resolve()
    project = root / "SceneryTools.xcodeproj"
    if not project.exists():
        raise RuntimeError("SceneryTools.xcodeproj not found; run in xptools repo root.")
    _run_command(
        [
            "xcodebuild",
            "-project",
            str(project),
            "-scheme",
            scheme,
            "-configuration",
            "Release",
        ],
        cwd=root,
    )


def _detect_solution_platform(solution: Path, configuration: str) -> str:
    try:
        lines = solution.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return "Win32"
    in_section = False
    platforms: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("GlobalSection(SolutionConfigurationPlatforms)"):
            in_section = True
            continue
        if in_section and stripped.startswith("EndGlobalSection"):
            break
        if in_section and "=" in stripped:
            left = stripped.split("=", 1)[0].strip()
            if left.lower().startswith(f"{configuration.lower()}|"):
                platforms.append(left.split("|", 1)[1].strip())
    if "x64" in platforms:
        return "x64"
    if "Win32" in platforms:
        return "Win32"
    return platforms[0] if platforms else "Win32"


def _detect_project_platform(project: Path, configuration: str) -> str:
    try:
        lines = project.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return "Win32"
    platforms: list[str] = []
    for line in lines:
        stripped = line.strip()
        if "ProjectConfiguration" not in stripped or "Include=" not in stripped:
            continue
        parts = stripped.split("Include=", 1)[1]
        quote = '"' if '"' in parts else "'"
        if quote not in parts:
            continue
        value = parts.split(quote, 2)[1]
        if value.lower().startswith(f"{configuration.lower()}|"):
            platforms.append(value.split("|", 1)[1].strip())
    if "x64" in platforms:
        return "x64"
    if "Win32" in platforms:
        return "Win32"
    return platforms[0] if platforms else "Win32"


def _detect_project_toolset(project: Path) -> str | None:
    try:
        lines = project.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for line in lines:
        stripped = line.strip()
        if "<PlatformToolset>" in stripped:
            value = stripped.replace("</PlatformToolset>", "")
            return value.split("<PlatformToolset>", 1)[1].strip()
    return None


def _msvc_arch_for_platform(platform: str) -> str:
    normalized = platform.lower()
    if normalized in ("x64", "amd64", "win64"):
        return "x64"
    return "x86"


def _short_path(path: Path) -> str:
    if os.name != "nt":
        return str(path)
    try:
        import ctypes  # noqa: PLC0415
    except ImportError:
        return str(path)
    buffer_size = 32768
    buffer = ctypes.create_unicode_buffer(buffer_size)
    size = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, buffer_size)
    if size == 0 or size >= buffer_size:
        return str(path)
    return buffer.value


def _available_msvc_toolsets(vcvarsall: Path | None) -> list[str]:
    if vcvarsall is None:
        return []
    vc_root = vcvarsall.parents[2]
    tools_root = vc_root / "Tools" / "MSVC"
    if not tools_root.exists():
        return []
    found: set[str] = set()
    for entry in tools_root.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if name.startswith("14.1"):
            found.add("v141")
        elif name.startswith("14.2"):
            found.add("v142")
        elif name.startswith("14."):
            found.add("v143")
    order = ["v141", "v142", "v143"]
    return [toolset for toolset in order if toolset in found]


def _pick_preferred_toolset(available: list[str]) -> str | None:
    for candidate in ("v143", "v142", "v141"):
        if candidate in available:
            return candidate
    return None

def _run_msvc_build(root: Path, target: str) -> None:
    root = root.resolve()
    project = root / "msvc" / target / f"{target}.vcxproj"
    if not project.exists():
        raise RuntimeError(
            f"{target}.vcxproj not found; run in xptools repo root."
        )
    msbuild = _find_msbuild()
    vcvarsall = _find_vcvarsall(msbuild)
    toolset_override = _detect_msvc_toolset(msbuild)
    if msbuild is None or vcvarsall is None:
        raise RuntimeError(
            "MSVC Build Tools not found; install Visual Studio 2017+ Build Tools "
            "(MSBuild + C++ workload) or set "
            f"{ENV_MSBUILD_PATH}/{ENV_VCVARSALL_PATH}."
        )
    platform = _detect_project_platform(project, "Release")
    project_toolset = _detect_project_toolset(project)
    available_toolsets = _available_msvc_toolsets(vcvarsall)
    preferred_toolset = _pick_preferred_toolset(available_toolsets)
    toolset = toolset_override or project_toolset
    sdk_version = _detect_windows_sdk_version()
    if toolset_override:
        toolset = toolset_override
    elif toolset is None or toolset.lower() == "v100":
        toolset = preferred_toolset or DEFAULT_MSVC_TOOLSET
    elif preferred_toolset and toolset not in available_toolsets:
        print(
            f"MSVC toolset {toolset} not found; using {preferred_toolset} instead."
        )
        toolset = preferred_toolset
    arch = _msvc_arch_for_platform(platform)
    vcvarsall_cmd = _short_path(vcvarsall)
    msbuild_cmd_path = _short_path(msbuild)
    project_cmd_path = _short_path(project)
    steps = [f"call {vcvarsall_cmd} {arch}"]
    msbuild_cmd = (
        f"{msbuild_cmd_path} {project_cmd_path} /m /t:Build "
        f'/p:Configuration=Release /p:Platform={platform}'
    )
    if toolset:
        msbuild_cmd += f" /p:PlatformToolset={toolset}"
    if sdk_version:
        msbuild_cmd += f" /p:WindowsTargetPlatformVersion={sdk_version}"
    steps.append(msbuild_cmd)
    cmd_line = " && ".join(steps)
    _run_command(["cmd", "/s", "/c", cmd_line], cwd=root)


def _find_tool(root: Path, names: Iterable[str]) -> Path | None:
    for name in names:
        for candidate in root.rglob(name):
            if candidate.is_file():
                return candidate
    return None


def _install_binaries(
    root: Path, install_dir: Path, tool_map: dict[str, Iterable[str]]
) -> list[BuiltTool]:
    install_dir.mkdir(parents=True, exist_ok=True)
    built: list[BuiltTool] = []
    for key, names in tool_map.items():
        found = _find_tool(root, names)
        if not found:
            raise RuntimeError(f"Built tool not found for {key}.")
        destination = install_dir / found.name
        shutil.copy2(found, destination)
        built.append(BuiltTool(key, destination))
    return built


def build_xptools(
    *,
    source_dir: Path,
    install_dir: Path,
    repo_url: str = XPTOOLS_REPO_URL,
    tag: str = XPTOOLS_TAG,
    commit: str | None = XPTOOLS_COMMIT,
    install_deps: bool = False,
    interactive: bool = True,
) -> list[BuiltTool]:
    ensure_build_deps(install=install_deps, interactive=interactive)
    _ensure_repo(source_dir, tag=tag, commit=commit, repo_url=repo_url)
    if os.name == "nt":
        for target in ("DSFTool", "DDSTool"):
            _run_msvc_build(source_dir, target)
    elif sys.platform == "darwin":
        for target in ("DSFTool", "DDSTool"):
            _run_xcodebuild(source_dir, target)
    else:
        for target in ("DSFTool", "DDSTool"):
            _run_make(source_dir, target)
    return _install_binaries(
        source_dir,
        install_dir,
        {
            "dsftool": ("DSFTool.exe", "DSFTool", "dsftool"),
            "ddstool": ("DDSTool.exe", "DDSTool", "ddstool"),
        },
    )


