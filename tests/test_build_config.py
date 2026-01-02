from __future__ import annotations

import json
from pathlib import Path

from dem2dsf.build_config import load_build_config


def test_load_build_config_normalizes(tmp_path: Path) -> None:
    payload = {
        "dem": "dem.tif",
        "tiles": "+47+008",
        "output_dir": "build",
        "options": {"fallback_dem": ["fallback.tif"]},
        "tools": {"dsftool": "DSFTool"},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    config = load_build_config(path)

    assert config.output_dir == "build"
    assert config.inputs["dems"] == ["dem.tif"]
    assert config.inputs["tiles"] == ["+47+008"]
    assert config.options["fallback_dem_paths"] == ["fallback.tif"]
    assert config.tools["dsftool"] == ["DSFTool"]
