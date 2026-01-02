from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dem2dsf import cli
from dem2dsf.backends.base import BuildResult
from dem2dsf.doctor import CheckResult


def test_cli_version() -> None:
    assert cli.main(["version"]) == 0


def test_default_ortho_runner() -> None:
    runner = cli._default_ortho_runner()
    assert runner is not None


def test_default_ortho_runner_meipass(monkeypatch, tmp_path: Path) -> None:
    runner_dir = tmp_path / "scripts"
    runner_dir.mkdir()
    runner_path = runner_dir / "ortho4xp_runner.py"
    runner_path.write_text("# stub", encoding="utf-8")

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert cli._default_ortho_runner() == [sys.executable, str(runner_path)]


def test_cli_build_requires_tile() -> None:
    with pytest.raises(SystemExit):
        cli.main(["build", "--dem", "dem.tif"])


def test_cli_build_requires_dem() -> None:
    with pytest.raises(SystemExit):
        cli.main(["build", "--tile", "+47+008"])


def test_cli_build_reports_errors(monkeypatch) -> None:
    def fake_run_build(**_kwargs):
        return BuildResult(build_plan={}, build_report={"errors": ["boom"]})

    monkeypatch.setattr(cli, "run_build", fake_run_build)

    result = cli.main(["build", "--dem", "dem.tif", "--tile", "+47+008"])
    assert result == 1


def test_cli_build_success(monkeypatch) -> None:
    def fake_run_build(**_kwargs):
        return BuildResult(build_plan={}, build_report={"errors": []})

    monkeypatch.setattr(cli, "run_build", fake_run_build)

    result = cli.main(["build", "--dem", "dem.tif", "--tile", "+47+008"])
    assert result == 0


def test_cli_build_infers_tiles(monkeypatch) -> None:
    captured = {}

    def fake_run_build(*, tiles, **_kwargs):
        captured["tiles"] = tiles
        return BuildResult(build_plan={}, build_report={"errors": []})

    def fake_infer_tiles(*_args, **_kwargs):
        return SimpleNamespace(tiles=["+47+008"], warnings=())

    monkeypatch.setattr(cli, "run_build", fake_run_build)
    monkeypatch.setattr(cli, "infer_tiles", fake_infer_tiles)

    result = cli.main(["build", "--dem", "dem.tif", "--infer-tiles"])
    assert result == 0
    assert captured["tiles"] == ["+47+008"]


def test_cli_build_with_config(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "inputs": {"dems": ["dem.tif"], "tiles": ["+47+008"]},
                "options": {"dry_run": True},
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_run_build(**kwargs):
        captured.update(kwargs)
        return BuildResult(build_plan={}, build_report={"errors": []})

    monkeypatch.setattr(cli, "run_build", fake_run_build)

    result = cli.main(["build", "--config", str(config_path), "--output", str(tmp_path)])
    assert result == 0
    assert captured["tiles"] == ["+47+008"]
    assert captured["dem_paths"][0].name == "dem.tif"


def test_cli_clean_dry_run(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    (build_dir / "normalized").mkdir(parents=True)

    result = cli.main(["clean", "--build-dir", str(build_dir)])

    assert result == 0
    assert (build_dir / "normalized").exists()


def test_cli_build_profile_options(monkeypatch) -> None:
    captured = {}

    def fake_run_build(*, options, **_kwargs):
        captured.update(options)
        return BuildResult(build_plan={}, build_report={"errors": []})

    monkeypatch.setattr(cli, "run_build", fake_run_build)

    result = cli.main(
        [
            "build",
            "--dem",
            "dem.tif",
            "--tile",
            "+47+008",
            "--profile",
            "--metrics-json",
            "metrics.json",
        ]
    )
    assert result == 0
    assert captured["profile"] is True
    assert captured["metrics_json"] == "metrics.json"


def test_cli_presets_list(capsys) -> None:
    result = cli.main(["presets", "list"])
    assert result == 0
    output = capsys.readouterr().out
    assert "usgs-13as" in output


def test_cli_presets_list_json(capsys) -> None:
    result = cli.main(["presets", "list", "--format", "json"])
    assert result == 0
    output = capsys.readouterr().out
    assert '"name": "usgs-13as"' in output


def test_cli_presets_show_text(capsys) -> None:
    result = cli.main(["presets", "show", "usgs-13as"])
    assert result == 0
    output = capsys.readouterr().out
    assert "Preset: usgs-13as" in output


def test_cli_presets_show_json(capsys) -> None:
    result = cli.main(["presets", "show", "usgs-13as", "--format", "json"])
    assert result == 0
    output = capsys.readouterr().out
    assert '"name": "usgs-13as"' in output


def test_cli_presets_unknown(capsys) -> None:
    result = cli.main(["presets", "show", "missing"])
    assert result == 1
    output = capsys.readouterr().err
    assert "Unknown preset" in output


def test_cli_presets_export_include_builtins(capsys) -> None:
    result = cli.main(["presets", "export", "--include-builtins"])
    assert result == 0
    output = capsys.readouterr().out
    assert '"name": "usgs-13as"' in output


def test_cli_presets_import_export_roundtrip(tmp_path: Path, capsys) -> None:
    input_payload = {
        "presets": [
            {
                "name": "custom",
                "summary": "Custom preset.",
                "inputs": [],
                "options": {"density": "low"},
                "notes": [],
                "example": "",
            }
        ]
    }
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(input_payload), encoding="utf-8")
    dest_path = tmp_path / "user_presets.json"

    result = cli.main(["presets", "import", str(input_path), "--user-path", str(dest_path)])
    assert result == 0
    capsys.readouterr()

    result = cli.main(["presets", "export", "--user-path", str(dest_path)])
    assert result == 0
    output = capsys.readouterr().out
    assert '"custom"' in output


def test_cli_presets_import_missing(tmp_path: Path, capsys) -> None:
    missing_path = tmp_path / "missing.json"
    result = cli.main(["presets", "import", str(missing_path)])
    assert result == 1
    output = capsys.readouterr().err
    assert "Preset file not found" in output


def test_cli_presets_import_invalid(tmp_path: Path, capsys) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{", encoding="utf-8")
    result = cli.main(["presets", "import", str(invalid_path)])
    assert result == 1
    output = capsys.readouterr().err
    assert "Failed to load presets" in output


def test_cli_presets_export_to_file(tmp_path: Path) -> None:
    output_path = tmp_path / "export.json"
    result = cli.main(["presets", "export", "--include-builtins", "--output", str(output_path)])
    assert result == 0
    assert output_path.exists()


def test_cli_wizard(monkeypatch, tmp_path: Path) -> None:
    called = {"ok": False}

    def fake_run_wizard(**_kwargs):
        called["ok"] = True

    monkeypatch.setattr(cli, "run_wizard", fake_run_wizard)

    result = cli.main(
        [
            "wizard",
            "--dem",
            "dem.tif",
            "--tile",
            "+47+008",
            "--output",
            str(tmp_path),
            "--defaults",
        ]
    )
    assert result == 0
    assert called["ok"] is True


def test_cli_tiles_command_json(monkeypatch, capsys) -> None:
    def fake_infer_tiles(*_args, **_kwargs):
        return SimpleNamespace(
            tiles=["+47+008"],
            bounds=(8.0, 47.0, 9.0, 48.0),
            dem_bounds=None,
            aoi_bounds=None,
            coverage={"+47+008": 1.0},
            warnings=(),
        )

    monkeypatch.setattr(cli, "infer_tiles", fake_infer_tiles)

    result = cli.main(["tiles", "--dem", "dem.tif", "--json"])
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tiles"] == ["+47+008"]


def test_cli_doctor_error(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "run_doctor",
        lambda **_kwargs: [CheckResult(name="python", status="error", detail="bad")],
    )

    assert cli.main(["doctor"]) == 1


def test_cli_doctor_success(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "run_doctor",
        lambda **_kwargs: [CheckResult(name="python", status="ok", detail="ok")],
    )

    assert cli.main(["doctor"]) == 0


def test_cli_autoortho_requires_tile(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: [sys.executable, "runner.py"])
    with pytest.raises(SystemExit):
        cli.main(["autoortho", "--dem", "dem.tif", "--ortho-root", "ortho"])


def test_cli_autoortho_requires_dem(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: [sys.executable, "runner.py"])
    with pytest.raises(SystemExit):
        cli.main(["autoortho", "--tile", "+47+008", "--ortho-root", "ortho"])


def test_cli_autoortho_missing_runner(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: None)
    with pytest.raises(SystemExit):
        cli.main(
            [
                "autoortho",
                "--dem",
                "dem.tif",
                "--tile",
                "+47+008",
                "--ortho-root",
                "ortho",
            ]
        )


def test_cli_autoortho_requires_ortho_root(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_tool_paths", lambda *_: {})
    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: [sys.executable, "runner.py"])
    with pytest.raises(SystemExit):
        cli.main(["autoortho", "--dem", "dem.tif", "--tile", "+47+008"])


def test_cli_autoortho_success(monkeypatch, tmp_path: Path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("print('ok')", encoding="utf-8")

    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: [sys.executable, str(runner)])
    monkeypatch.setattr(
        cli,
        "run_build",
        lambda **_kwargs: BuildResult(build_plan={}, build_report={"errors": []}),
    )

    result = cli.main(
        [
            "autoortho",
            "--dem",
            "dem.tif",
            "--tile",
            "+47+008",
            "--ortho-root",
            "ortho",
        ]
    )
    assert result == 0


def test_cli_autoortho_options(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: [sys.executable, "runner.py"])
    captured = {}

    def fake_run_build(*, options, **_kwargs):
        captured.update(options)
        return BuildResult(build_plan={}, build_report={"errors": []})

    monkeypatch.setattr(cli, "run_build", fake_run_build)

    result = cli.main(
        [
            "autoortho",
            "--dem",
            "dem.tif",
            "--tile",
            "+47+008",
            "--ortho-root",
            "ortho",
            "--batch",
            "--ortho-python",
            "python.exe",
        ]
    )
    assert result == 0
    assert "--batch" in captured["runner"]
    assert "python.exe" in captured["runner"]


def test_cli_autoortho_reports_errors(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: [sys.executable, "runner.py"])
    monkeypatch.setattr(
        cli,
        "run_build",
        lambda **_kwargs: BuildResult(build_plan={}, build_report={"errors": ["boom"]}),
    )
    result = cli.main(
        [
            "autoortho",
            "--dem",
            "dem.tif",
            "--tile",
            "+47+008",
            "--ortho-root",
            "ortho",
        ]
    )
    assert result == 1


def test_cli_build_uses_tool_paths(monkeypatch, tmp_path: Path) -> None:
    ortho_script = tmp_path / "ortho" / "Ortho4XP_v140.py"
    ortho_script.parent.mkdir()
    ortho_script.write_text("stub", encoding="utf-8")
    dsftool = tmp_path / "DSFTool.exe"
    dsftool.write_text("stub", encoding="utf-8")
    ddstool = tmp_path / "DDSTool.exe"
    ddstool.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "load_tool_paths",
        lambda *_: {"ortho4xp": ortho_script, "dsftool": dsftool, "ddstool": ddstool},
    )
    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: [sys.executable, "runner.py"])

    captured = {}

    def fake_run_build(*, options, **_kwargs):
        captured.update(options)
        return BuildResult(build_plan={}, build_report={"errors": []})

    monkeypatch.setattr(cli, "run_build", fake_run_build)

    result = cli.main(["build", "--dem", "dem.tif", "--tile", "+47+008"])
    assert result == 0
    assert captured["runner"][0] == sys.executable
    assert "--ortho-root" in captured["runner"]
    assert captured["dsftool"] == [str(dsftool)]
    assert captured["ddstool"] == [str(ddstool)]


def test_cli_publish_uses_tool_paths(monkeypatch, tmp_path: Path) -> None:
    sevenzip = tmp_path / "7z.exe"
    sevenzip.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(cli, "load_tool_paths", lambda *_: {"7zip": sevenzip})
    monkeypatch.setattr(cli, "find_sevenzip", lambda *_: None)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    captured = {}

    def fake_publish_build(*_args, **kwargs):
        captured.update(kwargs)
        return {"zip_path": "out.zip", "warnings": []}

    monkeypatch.setattr(cli, "publish_build", fake_publish_build)

    result = cli.main(
        [
            "publish",
            "--build-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.zip"),
            "--dsf-7z",
        ]
    )
    assert result == 0
    assert captured["sevenzip_path"] == sevenzip
    assert captured["mode"] == "full"


def test_cli_autoortho_uses_tool_paths(monkeypatch, tmp_path: Path) -> None:
    ortho_script = tmp_path / "ortho" / "Ortho4XP_v140.py"
    ortho_script.parent.mkdir()
    ortho_script.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(cli, "load_tool_paths", lambda *_: {"ortho4xp": ortho_script})
    monkeypatch.setattr(cli, "_default_ortho_runner", lambda: [sys.executable, "runner.py"])
    captured = {}

    def fake_run_build(*, options, **_kwargs):
        captured.update(options)
        return BuildResult(build_plan={}, build_report={"errors": []})

    monkeypatch.setattr(cli, "run_build", fake_run_build)

    result = cli.main(["autoortho", "--dem", "dem.tif", "--tile", "+47+008"])
    assert result == 0
    assert str(ortho_script.parent) in captured["runner"]


def test_cli_overlay_errors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli,
        "run_overlay",
        lambda **_kwargs: {"errors": ["boom"], "warnings": [], "output_dir": "out"},
    )

    result = cli.main(["overlay", "--output", str(tmp_path), "--texture", "x.dds"])
    assert result == 1


def test_cli_overlay_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli,
        "run_overlay",
        lambda **_kwargs: {"errors": [], "warnings": [], "output_dir": "out"},
    )

    result = cli.main(["overlay", "--output", str(tmp_path), "--texture", "x.dds"])
    assert result == 0


def test_cli_patch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli,
        "run_patch",
        lambda **_kwargs: {"output_dir": str(tmp_path)},
    )

    result = cli.main(
        [
            "patch",
            "--build-dir",
            str(tmp_path),
            "--patch",
            str(tmp_path / "plan.json"),
            "--runner",
            "runner",
        ]
    )
    assert result == 0


def test_cli_patch_overrides(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_run_patch(*, options_override=None, **_kwargs):
        if options_override:
            captured.update(options_override)
        return {"output_dir": str(tmp_path)}

    monkeypatch.setattr(cli, "run_patch", fake_run_patch)

    result = cli.main(
        [
            "patch",
            "--build-dir",
            str(tmp_path),
            "--patch",
            str(tmp_path / "plan.json"),
            "--dsftool",
            "dsf",
        ]
    )
    assert result == 0
    assert captured["dsftool"] == ["dsf"]


def test_cli_scan_conflicts(monkeypatch, tmp_path: Path) -> None:
    report = {"conflicts": ["a"]}
    monkeypatch.setattr(cli, "scan_custom_scenery", lambda *_args, **_kwargs: report)

    output = tmp_path / "scan.json"
    result = cli.main(["scan", "--scenery-root", str(tmp_path), "--output", str(output)])
    assert result == 1
    assert output.exists()


def test_cli_scan_no_conflicts(monkeypatch, tmp_path: Path) -> None:
    report = {"conflicts": []}
    monkeypatch.setattr(cli, "scan_custom_scenery", lambda *_args, **_kwargs: report)

    result = cli.main(["scan", "--scenery-root", str(tmp_path)])
    assert result == 0


def test_cli_cache_list(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "find_tile_cache_entries",
        lambda *_args, **_kwargs: {"osm": [Path("osm")], "elevation": [], "imagery": []},
    )
    result = cli.main(["cache", "list", "--ortho-root", str(tmp_path), "--tile", "+47+008"])
    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["tile"] == "+47+008"


def test_cli_cache_purge(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "purge_tile_cache_entries",
        lambda *_args, **_kwargs: {
            "tile": "+47+008",
            "dry_run": True,
            "entries": {},
            "removed": {},
        },
    )
    result = cli.main(["cache", "purge", "--ortho-root", str(tmp_path), "--tile", "+47+008"])
    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True


def test_cli_publish_missing_7z(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "find_sevenzip", lambda *_: None)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    with pytest.raises(SystemExit):
        cli.main(
            [
                "publish",
                "--build-dir",
                str(tmp_path),
                "--output",
                str(tmp_path / "out.zip"),
                "--dsf-7z",
            ]
        )


def test_cli_publish_detected_7z(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "find_sevenzip", lambda *_: Path("7z.exe"))
    captured = {}

    def fake_publish_build(*_args, **kwargs):
        captured.update(kwargs)
        return {"zip_path": "out.zip", "warnings": []}

    monkeypatch.setattr(cli, "publish_build", fake_publish_build)

    result = cli.main(
        [
            "publish",
            "--build-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.zip"),
            "--dsf-7z",
        ]
    )
    assert result == 0
    assert captured["sevenzip_path"] == Path("7z.exe")
    assert captured["mode"] == "full"


def test_cli_publish_prompt_for_7z(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "find_sevenzip", lambda *_: None)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "C:/fake/7z.exe")
    captured = {}

    def fake_publish_build(*_args, **kwargs):
        captured.update(kwargs)
        return {"zip_path": "out.zip", "warnings": []}

    monkeypatch.setattr(cli, "publish_build", fake_publish_build)

    result = cli.main(
        [
            "publish",
            "--build-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.zip"),
            "--dsf-7z",
        ]
    )
    assert result == 0
    assert captured["sevenzip_path"] == Path("C:/fake/7z.exe")
    assert captured["mode"] == "full"


def test_cli_publish_mode(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_publish_build(*_args, **kwargs):
        captured.update(kwargs)
        return {"zip_path": "out.zip", "warnings": []}

    monkeypatch.setattr(cli, "publish_build", fake_publish_build)

    result = cli.main(
        [
            "publish",
            "--build-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.zip"),
            "--mode",
            "scenery",
        ]
    )
    assert result == 0
    assert captured["mode"] == "scenery"


def test_cli_publish_prompt_blank_requires_allow(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "find_sevenzip", lambda *_: None)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "")

    with pytest.raises(SystemExit):
        cli.main(
            [
                "publish",
                "--build-dir",
                str(tmp_path),
                "--output",
                str(tmp_path / "out.zip"),
                "--dsf-7z",
            ]
        )


def test_cli_publish_with_warnings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli,
        "publish_build",
        lambda *_args, **_kwargs: {"zip_path": "out.zip", "warnings": ["warn"]},
    )

    result = cli.main(
        [
            "publish",
            "--build-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.zip"),
        ]
    )
    assert result == 0


def test_cli_unknown_command(monkeypatch) -> None:
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda *_args, **_kwargs: argparse.Namespace(command="unknown"),
    )
    with pytest.raises(SystemExit):
        cli.main(["unknown"])


def test_cli_unknown_command_returns_two(monkeypatch) -> None:
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda *_args, **_kwargs: argparse.Namespace(command="unknown"),
    )
    monkeypatch.setattr(argparse.ArgumentParser, "error", lambda *_: None)

    assert cli.main(["unknown"]) == 2


def test_cli_module_entrypoint(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["dem2dsf", "version"])
    sys.modules.pop("dem2dsf.cli", None)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("dem2dsf.cli", run_name="__main__")
    assert exc.value.code == 0
