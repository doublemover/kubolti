from __future__ import annotations

import json
from pathlib import Path

from dem2dsf.tools import config


def test_load_tool_paths_from_env(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "tool_paths.json"
    ortho_script = tmp_path / "ortho" / "Ortho4XP_v140.py"
    config_path.write_text(
        json.dumps(
            {
                "ortho4xp": str(ortho_script),
                "dsftool": str(tmp_path / "DSFTool.exe"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(config.ENV_TOOL_PATHS, str(config_path))

    tool_paths = config.load_tool_paths()

    assert tool_paths["ortho4xp"] == ortho_script
    assert tool_paths["dsftool"] == tmp_path / "DSFTool.exe"


def test_load_tool_paths_invalid_json(tmp_path: Path, monkeypatch) -> None:     
    config_path = tmp_path / "tool_paths.json"
    config_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv(config.ENV_TOOL_PATHS, str(config_path))

    assert config.load_tool_paths() == {}


def test_load_tool_paths_non_dict(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "tool_paths.json"
    config_path.write_text(json.dumps(["not", "dict"]), encoding="utf-8")
    monkeypatch.setenv(config.ENV_TOOL_PATHS, str(config_path))

    assert config.load_tool_paths() == {}


def test_load_tool_paths_explicit_path(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "tool_paths.json"
    ortho_script = tmp_path / "ortho" / "Ortho4XP_v140.py"
    config_path.write_text(
        json.dumps({"ortho4xp": str(ortho_script)}), encoding="utf-8"
    )
    monkeypatch.delenv(config.ENV_TOOL_PATHS, raising=False)

    tool_paths = config.load_tool_paths(config_path)
    assert tool_paths["ortho4xp"] == ortho_script


def test_load_tool_paths_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(config.ENV_TOOL_PATHS, raising=False)
    monkeypatch.chdir(tmp_path)
    ortho_script = tmp_path / "ortho" / "Ortho4XP_v140.py"
    tool_config = tmp_path / "tools" / "tool_paths.json"
    tool_config.parent.mkdir(parents=True, exist_ok=True)
    tool_config.write_text(
        json.dumps({"ortho4xp": str(ortho_script)}), encoding="utf-8"
    )

    tool_paths = config.load_tool_paths()
    assert tool_paths["ortho4xp"] == ortho_script


def test_load_tool_paths_no_candidates(monkeypatch) -> None:
    monkeypatch.delenv(config.ENV_TOOL_PATHS, raising=False)
    monkeypatch.setattr(config, "_default_candidate_paths", lambda: [])
    assert config.load_tool_paths() == {}


def test_ortho_root_from_paths(tmp_path: Path) -> None:
    ortho_script = tmp_path / "ortho" / "Ortho4XP_v140.py"
    tool_paths = {"ortho4xp": ortho_script}

    assert config.ortho_root_from_paths(tool_paths) == ortho_script.parent
