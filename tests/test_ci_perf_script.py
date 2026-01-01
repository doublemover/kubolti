from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_script(name: str):
    module_path = Path(__file__).resolve().parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_run_ci_perf_script(tmp_path: Path, monkeypatch) -> None:
    module = _load_script("run_ci_perf.py")
    output_dir = tmp_path / "perf"
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps({"normalize_seconds": 30.0, "publish_seconds": 30.0}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ci_perf.py",
            "--output-dir",
            str(output_dir),
            "--runs",
            "1",
            "--normalize-max-seconds",
            "30",
            "--publish-max-seconds",
            "30",
            "--baseline",
            str(baseline_path),
        ],
    )

    assert module.main() == 0
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "normalize" / "normalize.csv").exists()
    assert (output_dir / "publish" / "publish.csv").exists()
    assert (output_dir / "trend.json").exists()
    assert (output_dir / "trend.md").exists()
