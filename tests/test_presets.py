from __future__ import annotations

import json
from pathlib import Path

from dem2dsf import presets


def test_list_presets_sorted() -> None:
    names = [preset.name for preset in presets.list_presets()]
    assert names == sorted(names)
    assert "usgs-13as" in names


def test_get_preset_case_insensitive() -> None:
    preset = presets.get_preset("USGS-13AS")
    assert preset is not None
    assert preset.name == "usgs-13as"


def test_preset_as_dict() -> None:
    preset = presets.get_preset("srtm-fallback")
    assert preset is not None
    payload = presets.preset_as_dict(preset)
    assert payload["name"] == "srtm-fallback"
    assert "options" in payload


def test_format_preset() -> None:
    preset = presets.get_preset("eu-dem-utm")
    assert preset is not None
    formatted = presets.format_preset(preset)
    assert "Preset: eu-dem-utm" in formatted
    assert "Defaults:" in formatted


def test_load_user_presets_from_file(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "presets": [
            {
                "name": "custom",
                "summary": "My custom preset.",
                "inputs": ["demo"],
                "options": {"density": "low"},
                "notes": ["note"],
                "example": "python -m dem2dsf build --density low",
            }
        ],
    }
    preset_path = tmp_path / "presets.json"
    preset_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = presets.load_user_presets(preset_path)
    assert "custom" in loaded
    assert loaded["custom"].summary == "My custom preset."


def test_write_user_presets_roundtrip(tmp_path: Path) -> None:
    preset = presets.Preset(
        name="roundtrip",
        summary="Roundtrip preset.",
        inputs=(),
        options={"density": "medium"},
        notes=(),
        example="",
    )
    preset_path = tmp_path / "presets.json"
    presets.write_user_presets(preset_path, {"roundtrip": preset})

    loaded = presets.load_presets_file(preset_path)
    assert "roundtrip" in loaded
    assert loaded["roundtrip"].summary == "Roundtrip preset."


def test_user_preset_overrides_builtin(monkeypatch, tmp_path: Path) -> None:
    payload = {
        "presets": [
            {
                "name": "usgs-13as",
                "summary": "Override",
                "inputs": [],
                "options": {},
                "notes": [],
                "example": "",
            }
        ]
    }
    preset_path = tmp_path / "presets.json"
    preset_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv(presets.ENV_PRESETS_PATH, str(preset_path))

    preset = presets.get_preset("usgs-13as")
    assert preset is not None
    assert preset.summary == "Override"


def test_load_presets_file_with_list_payload(tmp_path: Path) -> None:
    payload = [
        {
            "name": "list-only",
            "summary": "List payload.",
            "inputs": "single",
            "options": {},
            "notes": 3,
            "example": "",
        },
        {"name": 5, "summary": "bad"},
    ]
    preset_path = tmp_path / "presets.json"
    preset_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = presets.load_presets_file(preset_path)
    assert loaded["list-only"].inputs == ("single",)
    assert loaded["list-only"].notes == ()


def test_load_presets_file_invalid_payload(tmp_path: Path) -> None:
    preset_path = tmp_path / "presets.json"
    preset_path.write_text(json.dumps("oops"), encoding="utf-8")
    loaded = presets.load_presets_file(preset_path)
    assert loaded == {}


def test_load_user_presets_invalid_json(tmp_path: Path) -> None:
    preset_path = tmp_path / "presets.json"
    preset_path.write_text("{", encoding="utf-8")
    loaded = presets.load_user_presets(preset_path)
    assert loaded == {}
