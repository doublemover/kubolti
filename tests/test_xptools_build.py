from __future__ import annotations

import builtins
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dem2dsf.tools import xptools_build as build


@pytest.mark.parametrize(
    ("os_name", "platform", "expected"),
    [
        ("nt", "win32", "msvc"),
        ("posix", "darwin", "xcode"),
        ("posix", "linux", "make"),
    ],
)
def test_build_xptools_calls_builder(
    tmp_path: Path, monkeypatch, os_name: str, platform: str, expected: str
) -> None:
    source_dir = tmp_path / "xptools-src"
    install_dir = tmp_path / "xptools"
    source_dir.mkdir()
    (source_dir / "DSFTool.exe").write_text("dsf", encoding="utf-8")
    (source_dir / "DDSTool.exe").write_text("dds", encoding="utf-8")

    monkeypatch.setattr(build.os, "name", os_name, raising=False)
    monkeypatch.setattr(build.sys, "platform", platform, raising=False)
    monkeypatch.setattr(build, "ensure_build_deps", lambda **_: None)
    monkeypatch.setattr(build, "_ensure_repo", lambda *_args, **_kwargs: None)

    called = {"msvc": 0, "xcode": 0, "make": 0}

    def mark(name: str):
        def _inner(*_args, **_kwargs):
            called[name] += 1

        return _inner

    monkeypatch.setattr(build, "_run_msvc_build", mark("msvc"))
    monkeypatch.setattr(build, "_run_xcodebuild", mark("xcode"))
    monkeypatch.setattr(build, "_run_make", mark("make"))

    tools = build.build_xptools(
        source_dir=source_dir,
        install_dir=install_dir,
        install_deps=False,
        interactive=False,
    )

    tool_map = {tool.name: tool.path for tool in tools}
    assert tool_map["dsftool"].exists()
    assert tool_map["ddstool"].exists()
    assert (install_dir / "DSFTool.exe").exists()
    assert (install_dir / "DDSTool.exe").exists()
    assert called[expected] == 2
    assert sum(called.values()) == 2


def test_run_command_raises(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=2)

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Command failed"):
        build._run_command(["fail"])


def test_prompt_eof(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    assert build._prompt("ok") == ""


def test_run_install_command_oserror(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr(build.subprocess, "run", boom)
    assert build._run_install_command(["noop"]) is False


def test_run_install_command_success(monkeypatch) -> None:
    monkeypatch.setattr(
        build.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0)
    )
    assert build._run_install_command(["ok"]) is True


def test_find_msbuild_env(monkeypatch, tmp_path: Path) -> None:
    msbuild = tmp_path / "MSBuild.exe"
    msbuild.write_text("bin", encoding="utf-8")
    monkeypatch.setenv(build.ENV_MSBUILD_PATH, str(msbuild))
    monkeypatch.setattr(build, "DEFAULT_MSBUILD_PATHS", [])
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf"))
    assert build._find_msbuild() == msbuild


def test_find_msbuild_defaults(monkeypatch, tmp_path: Path) -> None:
    msbuild = tmp_path / "MSBuild.exe"
    msbuild.write_text("bin", encoding="utf-8")
    monkeypatch.delenv(build.ENV_MSBUILD_PATH, raising=False)
    monkeypatch.setattr(build, "DEFAULT_MSBUILD_PATHS", [msbuild])
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf"))
    assert build._find_msbuild() == msbuild


def test_find_msbuild_scans_vs_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(build.ENV_MSBUILD_PATH, raising=False)
    monkeypatch.setattr(build, "DEFAULT_MSBUILD_PATHS", [])
    vs_root = tmp_path / "pf" / "Microsoft Visual Studio" / "2024" / "BuildTools"
    msbuild = vs_root / "MSBuild" / "Current" / "Bin" / "MSBuild.exe"
    msbuild.parent.mkdir(parents=True)
    msbuild.write_text("bin", encoding="utf-8")
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf"))
    assert build._find_msbuild() == msbuild


def test_find_vcvarsall_env(monkeypatch, tmp_path: Path) -> None:
    vcvars = tmp_path / "vcvarsall.bat"
    vcvars.write_text("bat", encoding="utf-8")
    monkeypatch.setenv(build.ENV_VCVARSALL_PATH, str(vcvars))
    monkeypatch.setattr(build, "DEFAULT_VCVARSALL_PATHS", [])
    assert build._find_vcvarsall() == vcvars


def test_find_vcvarsall_from_msbuild(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(build.ENV_VCVARSALL_PATH, raising=False)
    monkeypatch.setattr(build, "DEFAULT_VCVARSALL_PATHS", [])
    build_root = tmp_path / "BuildTools"
    msbuild = build_root / "MSBuild" / "Current" / "Bin" / "MSBuild.exe"
    vcvars = build_root / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
    msbuild.parent.mkdir(parents=True)
    vcvars.parent.mkdir(parents=True)
    msbuild.write_text("bin", encoding="utf-8")
    vcvars.write_text("bat", encoding="utf-8")
    assert build._find_vcvarsall(msbuild) == vcvars


def test_find_vcvarsall_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(build.ENV_VCVARSALL_PATH, raising=False)
    vcvars = tmp_path / "vcvarsall.bat"
    vcvars.write_text("bat", encoding="utf-8")
    monkeypatch.setattr(build, "DEFAULT_VCVARSALL_PATHS", [vcvars])
    assert build._find_vcvarsall() == vcvars


def test_find_vcvarsall_missing(monkeypatch) -> None:
    monkeypatch.delenv(build.ENV_VCVARSALL_PATH, raising=False)
    monkeypatch.setattr(build, "DEFAULT_VCVARSALL_PATHS", [])
    assert build._find_vcvarsall() is None


def test_detect_msvc_toolset_env(monkeypatch) -> None:
    monkeypatch.setenv(build.ENV_MSVC_TOOLSET, "v142")
    assert build._detect_msvc_toolset(None) == "v142"


def test_detect_msvc_toolset_default(monkeypatch) -> None:
    monkeypatch.delenv(build.ENV_MSVC_TOOLSET, raising=False)
    assert build._detect_msvc_toolset(None) is None


def test_install_mac_deps(monkeypatch) -> None:
    monkeypatch.setattr(build.shutil, "which", lambda name: "brew" if name == "brew" else None)
    monkeypatch.setattr(build, "_prompt", lambda *_: "y")
    monkeypatch.setattr(build, "_run_install_command", lambda *_: True)
    assert build._install_mac_deps(interactive=True) is True


def test_install_mac_deps_missing(monkeypatch) -> None:
    monkeypatch.setattr(build.shutil, "which", lambda *_: None)
    assert build._install_mac_deps(interactive=False) is False


def test_install_linux_deps_apt(monkeypatch) -> None:
    monkeypatch.setattr(
        build.shutil,
        "which",
        lambda name: "apt-get" if name == "apt-get" else None,
    )
    monkeypatch.setattr(build, "_prompt", lambda *_: "y")
    monkeypatch.setattr(build, "_run_install_command", lambda *_: True)
    assert build._install_linux_deps(interactive=True) is True


def test_install_linux_deps_dnf(monkeypatch) -> None:
    monkeypatch.setattr(build.shutil, "which", lambda name: "dnf" if name == "dnf" else None)
    monkeypatch.setattr(build, "_prompt", lambda *_: "y")
    monkeypatch.setattr(build, "_run_install_command", lambda *_: True)
    assert build._install_linux_deps(interactive=True) is True


def test_install_linux_deps_pacman(monkeypatch) -> None:
    monkeypatch.setattr(build.shutil, "which", lambda name: "pacman" if name == "pacman" else None)
    monkeypatch.setattr(build, "_prompt", lambda *_: "y")
    monkeypatch.setattr(build, "_run_install_command", lambda *_: True)
    assert build._install_linux_deps(interactive=True) is True


def test_install_linux_deps_missing(monkeypatch) -> None:
    monkeypatch.setattr(build.shutil, "which", lambda *_: None)
    assert build._install_linux_deps(interactive=False) is False


def test_ensure_build_deps_windows(monkeypatch, tmp_path: Path) -> None:
    msbuild = tmp_path / "MSBuild.exe"
    vcvars = tmp_path / "vcvarsall.bat"
    msbuild.write_text("bin", encoding="utf-8")
    vcvars.write_text("bat", encoding="utf-8")
    monkeypatch.setattr(build.os, "name", "nt", raising=False)
    monkeypatch.setattr(build, "_find_msbuild", lambda: msbuild)
    monkeypatch.setattr(build, "_find_vcvarsall", lambda *_: vcvars)
    monkeypatch.setattr(build.shutil, "which", lambda name: "git" if name == "git" else None)
    build.ensure_build_deps(install=False, interactive=False)


def test_ensure_build_deps_windows_git_missing(monkeypatch, tmp_path: Path) -> None:
    msbuild = tmp_path / "MSBuild.exe"
    vcvars = tmp_path / "vcvarsall.bat"
    msbuild.write_text("bin", encoding="utf-8")
    vcvars.write_text("bat", encoding="utf-8")
    monkeypatch.setattr(build.os, "name", "nt", raising=False)
    monkeypatch.setattr(build, "_find_msbuild", lambda: msbuild)
    monkeypatch.setattr(build, "_find_vcvarsall", lambda *_: vcvars)
    monkeypatch.setattr(build.shutil, "which", lambda *_: None)
    with pytest.raises(RuntimeError, match="git not found"):
        build.ensure_build_deps(install=False, interactive=False)


def test_ensure_build_deps_windows_install_does_not_autoinstall(monkeypatch) -> None:
    monkeypatch.setattr(build.os, "name", "nt", raising=False)
    monkeypatch.setattr(build, "_find_msbuild", lambda: None)
    monkeypatch.setattr(build, "_find_vcvarsall", lambda *_: None)
    monkeypatch.setattr(build.shutil, "which", lambda name: "git" if name == "git" else None)
    with pytest.raises(RuntimeError, match="MSVC Build Tools not found"):
        build.ensure_build_deps(install=True, interactive=False)


def test_ensure_build_deps_windows_missing(monkeypatch) -> None:
    monkeypatch.setattr(build.os, "name", "nt", raising=False)
    monkeypatch.setattr(build, "_find_msbuild", lambda: None)
    monkeypatch.setattr(build, "_find_vcvarsall", lambda *_: None)
    monkeypatch.setattr(build.shutil, "which", lambda name: "git" if name == "git" else None)
    with pytest.raises(RuntimeError, match="MSVC Build Tools not found"):
        build.ensure_build_deps(install=False, interactive=False)


def test_ensure_build_deps_posix_missing(monkeypatch) -> None:
    monkeypatch.setattr(build.os, "name", "posix", raising=False)
    monkeypatch.setattr(build.shutil, "which", lambda *_: None)
    with pytest.raises(RuntimeError, match="Missing build tools"):
        build.ensure_build_deps(install=False, interactive=False)


def test_ensure_build_deps_posix_install(monkeypatch) -> None:
    monkeypatch.setattr(build.os, "name", "posix", raising=False)
    monkeypatch.setattr(build.sys, "platform", "darwin", raising=False)
    calls = {"count": 0}

    def which(_name: str):
        calls["count"] += 1
        if calls["count"] <= 3:
            return None
        return "/usr/bin/tool"

    monkeypatch.setattr(build.shutil, "which", which)
    monkeypatch.setattr(build, "_install_mac_deps", lambda **_: True)
    build.ensure_build_deps(install=True, interactive=False)


def test_ensure_build_deps_posix_install_missing(monkeypatch) -> None:
    monkeypatch.setattr(build.os, "name", "posix", raising=False)
    monkeypatch.setattr(build.sys, "platform", "linux", raising=False)
    monkeypatch.setattr(build.shutil, "which", lambda *_: None)
    monkeypatch.setattr(build, "_install_linux_deps", lambda **_: True)
    with pytest.raises(RuntimeError, match="Missing build tools"):
        build.ensure_build_deps(install=True, interactive=False)


def test_ensure_repo_clone_and_commit(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    commands: list[list[str]] = []
    commit = "deadbeef"

    def record(command: list[str], *, cwd=None):
        commands.append(command)
        if "clone" in command:
            root.mkdir(parents=True, exist_ok=True)
            (root / ".gitmodules").write_text(
                "\n".join(
                    [
                        '[submodule "libs"]',
                        "path = libs",
                        "url = https://example.com/libs.git",
                        '[submodule "msvc_libs"]',
                        "path = msvc_libs",
                        "url = https://example.com/msvc_libs.git",
                    ]
                ),
                encoding="utf-8",
            )

    def fake_run(command, **_kwargs):
        if "rev-parse" in command:
            return SimpleNamespace(returncode=0, stdout=commit)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(build, "_run_command", record)
    monkeypatch.setattr(build.subprocess, "run", fake_run)
    build._ensure_repo(
        root,
        tag=build.XPTOOLS_TAG,
        commit=commit,
        repo_url=build.XPTOOLS_REPO_URL,
    )
    clone_cmd = next(cmd for cmd in commands if "clone" in cmd)
    assert "--recurse-submodules" in clone_cmd
    assert "--branch" not in clone_cmd
    checkout_index = next(
        i
        for i, cmd in enumerate(commands)
        if cmd[:4] == ["git", "-C", str(root), "checkout"]
    )
    submodule_index = next(
        i for i, cmd in enumerate(commands) if "submodule" in cmd and "update" in cmd
    )
    assert checkout_index < submodule_index


def test_ensure_repo_dirty(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    def fake_run(command, **_kwargs):
        if "status" in command:
            return SimpleNamespace(returncode=0, stdout=" M file")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(build, "_run_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(build.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="local changes"):
        build._ensure_repo(
            root,
            tag=build.XPTOOLS_TAG,
            commit=None,
            repo_url=build.XPTOOLS_REPO_URL,
        )


def test_ensure_repo_fetches_tags_when_missing(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        if "status" in command:
            return SimpleNamespace(returncode=0, stdout="")
        if "rev-parse" in command and any("refs/tags/" in part for part in command):
            return SimpleNamespace(returncode=1, stdout="")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(build, "_run_command", lambda command, **_kwargs: commands.append(command))
    monkeypatch.setattr(build.subprocess, "run", fake_run)
    build._ensure_repo(
        root,
        tag=build.XPTOOLS_TAG,
        commit=None,
        repo_url=build.XPTOOLS_REPO_URL,
    )
    assert ["git", "-C", str(root), "fetch", "--tags"] in commands


def test_ensure_repo_commit_verify_error(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    def fake_run(command, **_kwargs):
        if "status" in command:
            return SimpleNamespace(returncode=0, stdout="")
        if "rev-parse" in command and "refs/tags" in command:
            return SimpleNamespace(returncode=0, stdout="")
        if "rev-parse" in command and "HEAD" in command:
            return SimpleNamespace(returncode=1, stdout="")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(build, "_run_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(build.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Unable to verify xptools commit"):
        build._ensure_repo(
            root,
            tag=build.XPTOOLS_TAG,
            commit="deadbeef",
            repo_url=build.XPTOOLS_REPO_URL,
        )


def test_ensure_repo_commit_mismatch(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    commit = "cafebabe"

    def fake_run(command, **_kwargs):
        if "rev-parse" in command:
            return SimpleNamespace(returncode=0, stdout="deadbeef")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(build, "_run_command", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(build.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="xptools checkout does not match"):
        build._ensure_repo(
            root,
            tag=build.XPTOOLS_TAG,
            commit=commit,
            repo_url=build.XPTOOLS_REPO_URL,
        )


def test_ensure_repo_skips_missing_submodules(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".gitmodules").write_text("", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(build, "_run_command", lambda command, **_kwargs: commands.append(command))
    monkeypatch.setattr(
        build.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="")
    )
    build._ensure_repo(
        root,
        tag=build.XPTOOLS_TAG,
        commit=None,
        repo_url=build.XPTOOLS_REPO_URL,
    )
    assert not any(cmd[:5] == ["git", "-C", str(root), "submodule", "set-url"] for cmd in commands)


def test_run_make(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    captured = {}

    def record(command: list[str], *, cwd=None):
        captured["command"] = command
        captured["cwd"] = cwd

    monkeypatch.setattr(build, "_run_command", record)
    build._run_make(root, "DSFTool")
    assert captured["command"] == [
        "make",
        "CC=clang",
        "CXX=clang++",
        "conf=release_opt",
        "DSFTool",
    ]
    assert captured["cwd"] == root


def test_run_xcodebuild_missing_project(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(RuntimeError, match="SceneryTools.xcodeproj not found"):
        build._run_xcodebuild(root, "DSFTool")


def test_run_xcodebuild_success(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    project = root / "SceneryTools.xcodeproj"
    project.mkdir(parents=True)
    captured = {}

    def record(command: list[str], *, cwd=None):
        captured["command"] = command
        captured["cwd"] = cwd

    monkeypatch.setattr(build, "_run_command", record)
    build._run_xcodebuild(root, "DSFTool")
    assert captured["command"][:3] == ["xcodebuild", "-project", str(project)]
    assert "-scheme" in captured["command"]
    assert "DSFTool" in captured["command"]
    assert captured["cwd"] == root


def test_run_msvc_build_missing_solution(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(RuntimeError, match="DSFTool.vcxproj not found"):
        build._run_msvc_build(root, "DSFTool")


def test_run_msvc_build_missing_tools(monkeypatch, tmp_path: Path) -> None:     
    root = tmp_path / "repo"
    project = root / "msvc" / "DSFTool" / "DSFTool.vcxproj"
    project.parent.mkdir(parents=True)
    project.write_text("<Project />", encoding="utf-8")
    monkeypatch.setattr(build, "_find_msbuild", lambda: None)
    monkeypatch.setattr(build, "_find_vcvarsall", lambda *_: None)
    with pytest.raises(RuntimeError, match="MSVC Build Tools not found"):       
        build._run_msvc_build(root, "DSFTool")


def test_run_msvc_build_success(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    project = root / "msvc" / "DSFTool" / "DSFTool.vcxproj"
    project.parent.mkdir(parents=True)
    project.write_text(
        "\n".join(
            [
                "<Project>",
                '  <ProjectConfiguration Include="Release|Win32">',
                "    <Configuration>Release</Configuration>",
                "    <Platform>Win32</Platform>",
                "  </ProjectConfiguration>",
                "</Project>",
            ]
        ),
        encoding="utf-8",
    )
    msbuild = tmp_path / "MSBuild.exe"
    vcvars = tmp_path / "vcvarsall.bat"
    msbuild.write_text("bin", encoding="utf-8")
    vcvars.write_text("bat", encoding="utf-8")
    monkeypatch.setattr(build, "_find_msbuild", lambda: msbuild)
    monkeypatch.setattr(build, "_find_vcvarsall", lambda *_: vcvars)
    monkeypatch.setenv(build.ENV_MSVC_TOOLSET, "v141")

    captured = {}

    def record(command: list[str], *, cwd=None):
        captured["command"] = command
        captured["cwd"] = cwd

    monkeypatch.setattr(build, "_run_command", record)
    build._run_msvc_build(root, "DSFTool")
    assert captured["command"][0:3] == ["cmd", "/s", "/c"]
    cmd_line = captured["command"][3]
    assert "call" in cmd_line
    assert "/t:Build" in cmd_line
    assert "x86" in cmd_line
    assert "/p:PlatformToolset=v141" in cmd_line
    assert "/p:Platform=Win32" in cmd_line
    assert captured["cwd"] == root


def test_run_msvc_build_defaults_toolset(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    project = root / "msvc" / "DSFTool" / "DSFTool.vcxproj"
    project.parent.mkdir(parents=True)
    project.write_text(
        "\n".join(
            [
                "<Project>",
                '  <ProjectConfiguration Include="Release|Win32">',
                "    <Configuration>Release</Configuration>",
                "    <Platform>Win32</Platform>",
                "  </ProjectConfiguration>",
                "</Project>",
            ]
        ),
        encoding="utf-8",
    )
    msbuild = tmp_path / "MSBuild.exe"
    vcvars = tmp_path / "vcvarsall.bat"
    msbuild.write_text("bin", encoding="utf-8")
    vcvars.write_text("bat", encoding="utf-8")
    monkeypatch.setattr(build, "_find_msbuild", lambda: msbuild)
    monkeypatch.setattr(build, "_find_vcvarsall", lambda *_: vcvars)
    monkeypatch.setattr(build, "_detect_msvc_toolset", lambda *_: None)
    monkeypatch.setattr(build, "_available_msvc_toolsets", lambda *_: [])
    monkeypatch.setattr(build, "_detect_windows_sdk_version", lambda: None)
    captured = {}

    def record(command: list[str], *, cwd=None):
        captured["command"] = command
        captured["cwd"] = cwd

    monkeypatch.setattr(build, "_run_command", record)
    build._run_msvc_build(root, "DSFTool")
    cmd_line = captured["command"][3]
    assert f"/p:PlatformToolset={build.DEFAULT_MSVC_TOOLSET}" in cmd_line
    assert captured["cwd"] == root


def test_run_msvc_build_prefers_available_toolset(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "repo"
    project = root / "msvc" / "DSFTool" / "DSFTool.vcxproj"
    project.parent.mkdir(parents=True)
    project.write_text(
        "\n".join(
            [
                "<Project>",
                '  <ProjectConfiguration Include="Release|Win32">',
                "    <Configuration>Release</Configuration>",
                "    <Platform>Win32</Platform>",
                "  </ProjectConfiguration>",
                "  <PlatformToolset>v140</PlatformToolset>",
                "</Project>",
            ]
        ),
        encoding="utf-8",
    )
    msbuild = tmp_path / "MSBuild.exe"
    vcvars = tmp_path / "vcvarsall.bat"
    msbuild.write_text("bin", encoding="utf-8")
    vcvars.write_text("bat", encoding="utf-8")
    monkeypatch.setattr(build, "_find_msbuild", lambda: msbuild)
    monkeypatch.setattr(build, "_find_vcvarsall", lambda *_: vcvars)
    monkeypatch.setattr(build, "_detect_msvc_toolset", lambda *_: None)
    monkeypatch.setattr(build, "_available_msvc_toolsets", lambda *_: ["v142"])
    monkeypatch.setattr(build, "_detect_windows_sdk_version", lambda: None)
    printed: list[str] = []

    def record(command: list[str], *, cwd=None):
        printed.append(command[3])

    def capture_print(*args, **_kwargs) -> None:
        printed.append(" ".join(str(arg) for arg in args))

    monkeypatch.setattr(build, "_run_command", record)
    monkeypatch.setattr("builtins.print", capture_print)
    build._run_msvc_build(root, "DSFTool")
    assert any("MSVC toolset v140 not found" in message for message in printed)
    assert any("/p:PlatformToolset=v142" in message for message in printed)

def test_detect_solution_platform_defaults_win32(tmp_path: Path) -> None:
    solution = tmp_path / "XPTools.sln"
    solution.write_text("noop", encoding="utf-8")
    assert build._detect_solution_platform(solution, "Release") == "Win32"


def test_detect_solution_platform_oserror(tmp_path: Path) -> None:
    solution = tmp_path / "missing.sln"
    assert build._detect_solution_platform(solution, "Release") == "Win32"


def test_detect_solution_platform_prefers_x64(tmp_path: Path) -> None:
    solution = tmp_path / "XPTools.sln"
    solution.write_text(
        "\n".join(
            [
                "Global",
                "  GlobalSection(SolutionConfigurationPlatforms) = preSolution",
                "    Release|Win32 = Release|Win32",
                "    Release|x64 = Release|x64",
                "  EndGlobalSection",
                "EndGlobal",
            ]
        ),
        encoding="utf-8",
    )
    assert build._detect_solution_platform(solution, "Release") == "x64"


def test_detect_solution_platform_win32_only(tmp_path: Path) -> None:
    solution = tmp_path / "XPTools.sln"
    solution.write_text(
        "\n".join(
            [
                "Global",
                "  GlobalSection(SolutionConfigurationPlatforms) = preSolution",
                "    Release|Win32 = Release|Win32",
                "  EndGlobalSection",
                "EndGlobal",
            ]
        ),
        encoding="utf-8",
    )
    assert build._detect_solution_platform(solution, "Release") == "Win32"


def test_detect_project_platform_prefers_x64(tmp_path: Path) -> None:
    project = tmp_path / "Tool.vcxproj"
    project.write_text(
        "\n".join(
            [
                "<Project>",
                '  <ProjectConfiguration Include="Release|Win32" />',
                '  <ProjectConfiguration Include="Release|x64" />',
                "</Project>",
            ]
        ),
        encoding="utf-8",
    )
    assert build._detect_project_platform(project, "Release") == "x64"


def test_detect_project_platform_oserror(tmp_path: Path) -> None:
    project = tmp_path / "missing.vcxproj"
    assert build._detect_project_platform(project, "Release") == "Win32"


def test_detect_project_platform_skips_unquoted_include(tmp_path: Path) -> None:
    project = tmp_path / "Tool.vcxproj"
    project.write_text(
        "\n".join(
            [
                "<Project>",
                "  <ProjectConfiguration Include=Release|Win32 />",
                "</Project>",
            ]
        ),
        encoding="utf-8",
    )
    assert build._detect_project_platform(project, "Release") == "Win32"


def test_detect_project_platform_falls_back_to_first(tmp_path: Path) -> None:
    project = tmp_path / "Tool.vcxproj"
    project.write_text(
        "\n".join(
            [
                "<Project>",
                '  <ProjectConfiguration Include="Release|ARM" />',
                "</Project>",
            ]
        ),
        encoding="utf-8",
    )
    assert build._detect_project_platform(project, "Release") == "ARM"


def test_detect_project_toolset(tmp_path: Path) -> None:
    project = tmp_path / "Tool.vcxproj"
    project.write_text(
        "\n".join(
            [
                "<Project>",
                "  <PlatformToolset>v143</PlatformToolset>",
                "</Project>",
            ]
        ),
        encoding="utf-8",
    )
    assert build._detect_project_toolset(project) == "v143"


def test_detect_project_toolset_oserror(tmp_path: Path) -> None:
    project = tmp_path / "missing.vcxproj"
    assert build._detect_project_toolset(project) is None


def test_parse_sdk_version_invalid() -> None:
    assert build._parse_sdk_version("nope") is None
    assert build._parse_sdk_version("10.0.bad") is None


def test_detect_windows_sdk_version_env(monkeypatch) -> None:
    monkeypatch.setenv(build.ENV_WINDOWS_SDK_VERSION, "10.0.19041.0")
    assert build._detect_windows_sdk_version() == "10.0.19041.0"


def test_detect_windows_sdk_version_missing_kits(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(build.ENV_WINDOWS_SDK_VERSION, raising=False)
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf"))
    assert build._detect_windows_sdk_version() is None


def test_detect_windows_sdk_version_no_versions(monkeypatch, tmp_path: Path) -> None:
    kits_root = tmp_path / "pf" / "Windows Kits" / "10" / "Lib"
    kits_root.mkdir(parents=True)
    (kits_root / "not-a-version").mkdir()
    (kits_root / "10.0.1234.0").write_text("file", encoding="utf-8")
    monkeypatch.delenv(build.ENV_WINDOWS_SDK_VERSION, raising=False)
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf"))
    assert build._detect_windows_sdk_version() is None


def test_detect_windows_sdk_version_scans_kits(monkeypatch, tmp_path: Path) -> None:
    kits_root = tmp_path / "pf" / "Windows Kits" / "10" / "Lib"
    (kits_root / "10.0.19041.0").mkdir(parents=True)
    (kits_root / "10.0.22621.0").mkdir(parents=True)
    monkeypatch.delenv(build.ENV_WINDOWS_SDK_VERSION, raising=False)
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf"))
    assert build._detect_windows_sdk_version() == "10.0.22621.0"


def test_find_msbuild_skips_non_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(build.ENV_MSBUILD_PATH, raising=False)
    monkeypatch.setattr(build, "DEFAULT_MSBUILD_PATHS", [])
    vs_root = tmp_path / "pf" / "Microsoft Visual Studio"
    vs_root.mkdir(parents=True)
    (vs_root / "2024").write_text("file", encoding="utf-8")
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf"))
    assert build._find_msbuild() is None


def test_available_msvc_toolsets(tmp_path: Path) -> None:
    vcvars = tmp_path / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
    vcvars.parent.mkdir(parents=True)
    vcvars.write_text("bat", encoding="utf-8")
    tools_root = tmp_path / "VC" / "Tools" / "MSVC"
    (tools_root / "14.16.9999").mkdir(parents=True)
    (tools_root / "14.29.9999").mkdir()
    (tools_root / "14.44.9999").mkdir()
    assert build._available_msvc_toolsets(vcvars) == ["v141", "v142", "v143"]


def test_available_msvc_toolsets_missing() -> None:
    assert build._available_msvc_toolsets(None) == []


def test_available_msvc_toolsets_skips_files(tmp_path: Path) -> None:
    vcvars = tmp_path / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
    vcvars.parent.mkdir(parents=True)
    vcvars.write_text("bat", encoding="utf-8")
    tools_root = tmp_path / "VC" / "Tools" / "MSVC"
    tools_root.mkdir(parents=True)
    (tools_root / "not-a-dir").write_text("file", encoding="utf-8")
    assert build._available_msvc_toolsets(vcvars) == []


def test_pick_preferred_toolset() -> None:
    assert build._pick_preferred_toolset(["v143"]) == "v143"
    assert build._pick_preferred_toolset(["v142", "v143"]) == "v143"


def test_msvc_arch_for_platform_x64() -> None:
    assert build._msvc_arch_for_platform("Win64") == "x64"


def test_short_path_non_windows(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(build.os, "name", "posix", raising=False)
    path = tmp_path / "demo"
    assert build._short_path(path) == str(path)


def test_short_path_import_error(monkeypatch, tmp_path: Path) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "ctypes":
            raise ImportError("no ctypes")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(build.os, "name", "nt", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    path = tmp_path / "demo"
    assert build._short_path(path) == str(path)


def test_short_path_returns_original_on_failure(monkeypatch, tmp_path: Path) -> None:
    dummy_ctypes = SimpleNamespace(
        create_unicode_buffer=lambda _size: object(),
        windll=SimpleNamespace(
            kernel32=SimpleNamespace(GetShortPathNameW=lambda *_args: 0)
        ),
    )
    monkeypatch.setattr(build.os, "name", "nt", raising=False)
    monkeypatch.setitem(sys.modules, "ctypes", dummy_ctypes)
    path = tmp_path / "demo"
    assert build._short_path(path) == str(path)

def test_find_tool_missing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    assert build._find_tool(root, ["Nope"]) is None


def test_install_binaries_missing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(RuntimeError, match="Built tool not found"):
        build._install_binaries(root, tmp_path / "install", {"dsftool": ("DSFTool",)})
