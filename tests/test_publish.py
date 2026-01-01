from __future__ import annotations

import json
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from dem2dsf import publish
from dem2dsf.publish import _sevenzip_command, find_sevenzip, publish_build
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path


def test_publish_build(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")
    (build_dir / "terrain").mkdir()
    (build_dir / "terrain" / "tile.ter").write_text("ter", encoding="utf-8")

    output_zip = tmp_path / "out.zip"
    result = publish_build(build_dir, output_zip)

    assert Path(result["zip_path"]).exists()
    manifest = json.loads((build_dir / "manifest.json").read_text(encoding="utf-8"))
    assert any(entry["path"].endswith("+47+008.dsf") for entry in manifest["files"])
    assert (build_dir / "audit_report.json").exists()

    with ZipFile(output_zip) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert "audit_report.json" in names


def test_publish_build_sevenzip_fallback(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    output_zip = tmp_path / "out.zip"
    result = publish_build(
        build_dir,
        output_zip,
        dsf_7z=True,
        sevenzip_path=tmp_path / "missing-7z",
        allow_missing_sevenzip=True,
    )
    assert result["warnings"]
    assert not dsf_path.with_name(f"{dsf_path.name}.7z").exists()


def test_publish_build_sevenzip_stub(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    sevenzip = tmp_path / "sevenzip.py"
    sevenzip.write_text(
        "\n".join(
            [
                "import sys",
                "from pathlib import Path",
                "archive_path = Path(sys.argv[-2])",
                "archive_path.write_text('7z', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_zip = tmp_path / "out.zip"
    result = publish_build(
        build_dir,
        output_zip,
        dsf_7z=True,
        sevenzip_path=sevenzip,
    )
    assert not result["warnings"]
    assert dsf_path.read_text(encoding="utf-8") == "7z"
    assert not dsf_path.with_name(f"{dsf_path.name}.7z").exists()
    assert not dsf_path.with_suffix(f"{dsf_path.suffix}.uncompressed").exists()


def test_publish_build_sevenzip_backup(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    sevenzip = tmp_path / "sevenzip.py"
    sevenzip.write_text(
        "\n".join(
            [
                "import sys",
                "from pathlib import Path",
                "archive_path = Path(sys.argv[-2])",
                "archive_path.write_text('7z', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    publish_build(
        build_dir,
        tmp_path / "out.zip",
        dsf_7z=True,
        dsf_7z_backup=True,
        sevenzip_path=sevenzip,
    )
    backup_path = dsf_path.with_suffix(f"{dsf_path.suffix}.uncompressed")
    assert backup_path.exists()


def test_publish_build_requires_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Build directory not found"):
        publish_build(tmp_path / "missing", tmp_path / "out.zip")


def test_publish_build_requires_sevenzip(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="7z not found"):
        publish_build(
            build_dir,
            tmp_path / "out.zip",
            dsf_7z=True,
            sevenzip_path=tmp_path / "missing-7z",
            allow_missing_sevenzip=False,
        )


def test_publish_build_sevenzip_failure(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    sevenzip = tmp_path / "sevenzip.py"
    sevenzip.write_text(
        "\n".join(
            [
                "import sys",
                "sys.stderr.write('boom')",
                "sys.exit(1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="7z compression failed"):
        publish_build(
            build_dir,
            tmp_path / "out.zip",
            dsf_7z=True,
            sevenzip_path=sevenzip,
        )


def test_find_sevenzip_explicit_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.exe"
    assert find_sevenzip(missing) is None


def test_sevenzip_command_for_python_script(tmp_path: Path) -> None:
    script_path = tmp_path / "sevenzip.py"
    script_path.write_text("print('noop')\n", encoding="utf-8")
    command = _sevenzip_command(script_path)
    assert command[0] == sys.executable


def test_sevenzip_command_for_binary(tmp_path: Path) -> None:
    binary = tmp_path / "7z.exe"
    binary.write_text("stub", encoding="utf-8")
    command = _sevenzip_command(binary)
    assert command == [str(binary)]


def test_find_sevenzip_candidate(monkeypatch, tmp_path: Path) -> None:
    candidate = tmp_path / "7-Zip" / "7z.exe"
    candidate.parent.mkdir()
    candidate.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(publish.shutil, "which", lambda *_: None)
    monkeypatch.setattr(publish.os, "name", "nt")
    monkeypatch.setattr(
        publish.os,
        "environ",
        {"ProgramFiles": str(tmp_path), "ProgramFiles(x86)": str(tmp_path)},
    )

    assert find_sevenzip() == candidate


def test_find_sevenzip_from_which(monkeypatch, tmp_path: Path) -> None:
    sevenzip = tmp_path / "7z.exe"
    sevenzip.write_text("stub", encoding="utf-8")
    monkeypatch.setattr(publish.shutil, "which", lambda *_: str(sevenzip))

    assert find_sevenzip() == sevenzip


def test_find_sevenzip_darwin_candidates(monkeypatch) -> None:
    monkeypatch.setattr(publish.shutil, "which", lambda *_: None)
    monkeypatch.setattr(publish.os, "name", "posix")
    monkeypatch.setattr(publish.sys, "platform", "darwin")

    def fake_exists(path: Path) -> bool:
        return str(path) == "/opt/homebrew/bin/7z"

    monkeypatch.setattr(Path, "exists", fake_exists)

    assert find_sevenzip() == Path("/opt/homebrew/bin/7z")


def test_find_sevenzip_linux_candidates_missing(monkeypatch) -> None:
    monkeypatch.setattr(publish.shutil, "which", lambda *_: None)
    monkeypatch.setattr(publish.os, "name", "posix")
    monkeypatch.setattr(publish.sys, "platform", "linux")
    monkeypatch.setattr(Path, "exists", lambda *_: False)

    assert find_sevenzip() is None


def test_compress_dsf_archives_removes_existing(monkeypatch, tmp_path: Path) -> None:
    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_text("dsf", encoding="utf-8")
    archive_path = dsf_path.with_name(f"{dsf_path.name}.7z")
    archive_path.write_text("old", encoding="utf-8")

    class DummyResult:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(*_args, **kwargs):
        archive = Path(kwargs["cwd"]) / "tile.dsf.7z"
        archive.write_text("7z", encoding="utf-8")
        return DummyResult()

    monkeypatch.setattr(publish.subprocess, "run", fake_run)

    errors = publish._compress_dsf_archives(tmp_path / "7z.exe", [dsf_path])
    assert errors == []
    assert not archive_path.exists()
    assert dsf_path.read_text(encoding="utf-8") == "7z"
