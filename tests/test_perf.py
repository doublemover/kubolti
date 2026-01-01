from __future__ import annotations

import time
from pathlib import Path

from dem2dsf.perf import PerfTracker, resolve_metrics_path


def test_perf_tracker_records_spans() -> None:
    perf = PerfTracker(enabled=True, track_memory=True)
    perf.start()
    with perf.span("step"):
        time.sleep(0.001)
    perf.stop()

    summary = perf.summary()
    assert summary["total_seconds"] >= 0
    assert summary["spans"]["step"]["count"] == 1
    assert "peak_memory_mb" in summary


def test_perf_tracker_disabled_is_empty() -> None:
    perf = PerfTracker(enabled=False, track_memory=True)
    perf.start()
    with perf.span("noop"):
        pass
    perf.stop()
    assert perf.summary() == {}


def test_resolve_metrics_path_from_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DEM2DSF_PROFILE_DIR", str(tmp_path))
    resolved = resolve_metrics_path(tmp_path, None)
    assert resolved == tmp_path / "build_metrics.json"


def test_resolve_metrics_path_from_arg(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEM2DSF_PROFILE_DIR", raising=False)
    path = tmp_path / "metrics.json"
    resolved = resolve_metrics_path(tmp_path, str(path))
    assert resolved == path


def test_resolve_metrics_path_default_none(monkeypatch) -> None:
    monkeypatch.delenv("DEM2DSF_PROFILE_DIR", raising=False)
    assert resolve_metrics_path(Path("."), None) is None
