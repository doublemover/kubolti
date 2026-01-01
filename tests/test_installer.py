from __future__ import annotations

import os
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from dem2dsf.tools import installer


def _make_zip(path: Path, member: str, content: bytes | str = "data") -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, content)
    return path


def _make_tar(path: Path, member: str, content: bytes | str = "data") -> Path:
    member_path = path.parent / member
    member_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        member_path.write_bytes(content)
    else:
        member_path.write_text(content, encoding="utf-8")
    with tarfile.open(path, "w") as archive:
        archive.add(member_path, arcname=member)
    return path


def _exe_name(base: str) -> str:
    return f"{base}.exe" if os.name == "nt" else base


def _exe_payload() -> bytes:
    return b"\x7fELF\x02\x01\x01"


def _write_executable(path: Path) -> None:
    if os.name == "nt":
        path.write_text("stub", encoding="utf-8")
        return
    path.write_bytes(_exe_payload())
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_is_url() -> None:
    assert installer.is_url("https://example.com/file.zip")
    assert installer.is_url("file:///C:/tmp/file.zip")
    assert not installer.is_url("C:/tmp/file.zip")


def test_download_file_from_file_url(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    destination = tmp_path / "out.txt"

    installer.download_file(source.as_uri(), destination)

    assert destination.read_text(encoding="utf-8") == "payload"


def test_extract_archive_zip(tmp_path: Path) -> None:
    archive = _make_zip(tmp_path / "tool.zip", "root/DSFTool.exe")
    destination = tmp_path / "unzipped"

    roots = installer.extract_archive(archive, destination)

    assert (destination / "root" / "DSFTool.exe").exists()
    assert (destination / "root") in roots


def test_extract_archive_zip_with_directory(tmp_path: Path) -> None:
    archive = tmp_path / "tool.zip"
    with zipfile.ZipFile(archive, "w") as zipf:
        zipf.writestr("root/", "")
        zipf.writestr("root/readme.txt", "data")
        zipf.writestr("", "")

    destination = tmp_path / "unzipped"
    roots = installer.extract_archive(archive, destination)

    assert (destination / "root").exists()
    assert (destination / "root") in roots


def test_extract_archive_tar(tmp_path: Path) -> None:
    archive = _make_tar(tmp_path / "tool.tar", "root/DSFTool.exe")
    destination = tmp_path / "untarred"

    roots = installer.extract_archive(archive, destination)

    assert (destination / "root" / "DSFTool.exe").exists()
    assert (destination / "root") in roots


def test_extract_archive_tar_empty_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "empty.tar"
    archive.write_text("stub", encoding="utf-8")

    class DummyArchive:
        def __enter__(self) -> "DummyArchive":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def getmembers(self) -> list[object]:
            return [type("Member", (), {"name": ""})()]

        def extractall(self, *_args: object, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(installer.zipfile, "is_zipfile", lambda *_: False)
    monkeypatch.setattr(installer.tarfile, "is_tarfile", lambda *_: True)
    monkeypatch.setattr(installer.tarfile, "open", lambda *_a, **_k: DummyArchive())

    destination = tmp_path / "out"
    roots = installer.extract_archive(archive, destination)

    assert roots == []


def test_extract_archive_unknown_format(tmp_path: Path) -> None:
    archive = tmp_path / "tool.bin"
    archive.write_bytes(b"not an archive")

    with pytest.raises(ValueError, match="Unsupported archive format"):
        installer.extract_archive(archive, tmp_path / "out")


def test_safe_extract_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes target directory"):
        installer._safe_extract_path(tmp_path, Path("../escape"))


def test_safe_extract_path_rejects_prefix_bypass(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes target directory"):
        installer._safe_extract_path(root, Path("../root2/evil.txt"))


def test_find_executable_in_search_dirs(tmp_path: Path) -> None:
    tool_dir = tmp_path / "tool"
    tool_dir.mkdir()
    tool_path = tool_dir / _exe_name("DSFTool")
    _write_executable(tool_path)

    found = installer._find_executable([tool_path.name], [tool_dir])
    assert found == tool_path


def test_find_in_tree(tmp_path: Path) -> None:
    nested = tmp_path / "nest" / _exe_name("DSFTool")
    nested.parent.mkdir(parents=True)
    _write_executable(nested)

    found = installer._find_in_tree(tmp_path, [nested.name])
    assert found == nested


def test_find_executable_with_which(monkeypatch, tmp_path: Path) -> None:
    tool_path = tmp_path / _exe_name("dsf")
    _write_executable(tool_path)

    monkeypatch.setattr(installer.shutil, "which", lambda name: str(tool_path))
    found = installer._find_executable([tool_path.name], [])
    assert found == tool_path


def test_find_executable_missing(monkeypatch) -> None:
    monkeypatch.setattr(installer.shutil, "which", lambda *_: None)
    assert installer._find_executable(["Missing.exe"], []) is None


def test_find_dsftool_in_dir(tmp_path: Path) -> None:
    tool_dir = tmp_path / "tools"
    tool_dir.mkdir()
    tool_path = tool_dir / _exe_name("DSFTool")
    _write_executable(tool_path)

    assert installer.find_dsftool([tool_dir]) == tool_path


def test_install_from_archive_finds_executable(tmp_path: Path) -> None:
    exe_name = _exe_name("DSFTool")
    archive = _make_zip(
        tmp_path / "tool.zip", f"pkg/{exe_name}", content=_exe_payload()
    )
    destination = tmp_path / "install"

    result = installer.install_from_archive(
        archive,
        destination,
        executable_names=(exe_name,),
    )

    assert result.name == exe_name


def test_install_from_url_file(tmp_path: Path) -> None:
    exe_name = _exe_name("DSFTool")
    archive = _make_zip(
        tmp_path / "tool.zip", f"pkg/{exe_name}", content=_exe_payload()
    )
    destination = tmp_path / "download"

    result = installer.install_from_url(
        archive.as_uri(),
        destination,
        executable_names=(exe_name,),
    )

    assert result.name == exe_name


def test_find_ortho4xp_in_dir(tmp_path: Path) -> None:
    script = tmp_path / "Ortho4XP_v140.py"
    script.write_text("print('ok')", encoding="utf-8")

    found = installer.find_ortho4xp([tmp_path])

    assert found == script


def test_find_ortho4xp_missing(tmp_path: Path) -> None:
    found = installer.find_ortho4xp([tmp_path])
    assert found is None


def test_install_ortho4xp_requires_git(tmp_path: Path, monkeypatch) -> None:    
    monkeypatch.setattr(installer.shutil, "which", lambda *_: None)
    with pytest.raises(RuntimeError, match="git is required"):
        installer.install_ortho4xp("https://example.com/repo.git", tmp_path / "ortho")


def test_install_ortho4xp_git_clone(monkeypatch, tmp_path: Path) -> None:
    destination = tmp_path / "ortho"
    clone_args: list[str] = []

    monkeypatch.setattr(installer.shutil, "which", lambda *_: "git")
    monkeypatch.setattr(
        installer.subprocess,
        "check_call",
        lambda args: clone_args.extend(args),
    )
    script_path = destination / "Ortho4XP_v140.py"
    monkeypatch.setattr(installer, "find_ortho4xp_script", lambda *_: script_path)

    result = installer.install_ortho4xp("https://example.com/repo.git", destination)

    assert clone_args == [
        "git",
        "clone",
        "https://example.com/repo.git",
        str(destination),
    ]
    assert result == script_path


def test_install_ortho4xp_from_archive(tmp_path: Path) -> None:
    archive = _make_zip(tmp_path / "ortho.zip", "Ortho4XP/Ortho4XP_v140.py")    
    destination = tmp_path / "ortho"

    script = installer.install_ortho4xp(archive.as_uri(), destination)

    assert script.name == "Ortho4XP_v140.py"


def test_install_ortho4xp_archive_replaces_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "ortho"
    destination.mkdir()
    (destination / "old.txt").write_text("old", encoding="utf-8")
    root_dir = tmp_path / "Ortho4XP"
    root_dir.mkdir()
    (root_dir / "Ortho4XP_v140.py").write_text("print('ok')", encoding="utf-8")
    real_rmtree = shutil.rmtree
    removed = {"called": False}

    def fake_download(_url: str, dest: Path) -> Path:
        dest.write_text("stub", encoding="utf-8")
        return dest

    def fake_rmtree(path: Path) -> None:
        removed["called"] = True
        real_rmtree(path)

    monkeypatch.setattr(installer, "download_file", fake_download)
    monkeypatch.setattr(installer, "extract_archive", lambda *_: [root_dir])
    monkeypatch.setattr(installer.shutil, "rmtree", fake_rmtree)

    script = installer.install_ortho4xp("https://example.com/archive.zip", destination)

    assert removed["called"] is True
    assert script == destination / "Ortho4XP_v140.py"


def test_ensure_sevenzip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sevenzip = tmp_path / "7z.exe"
    sevenzip.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(installer, "find_sevenzip", lambda *_: sevenzip)

    result = installer.ensure_sevenzip()

    assert result.status == "ok"
    assert result.path == sevenzip


def test_install_from_archive_missing_executable(tmp_path: Path) -> None:
    archive = _make_zip(tmp_path / "tool.zip", "pkg/readme.txt")
    with pytest.raises(FileNotFoundError, match="Executable not found"):
        installer.install_from_archive(
            archive,
            tmp_path / "install",
            executable_names=("Missing.exe",),
        )


def test_ensure_sevenzip_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "find_sevenzip", lambda *_: None)
    result = installer.ensure_sevenzip()
    assert result.status == "missing"


def test_ensure_tool_config(tmp_path: Path) -> None:
    config = installer.ensure_tool_config(
        tmp_path / "tool_paths.json", {"dsftool": tmp_path / "DSFTool.exe"}
    )

    assert config.exists()
