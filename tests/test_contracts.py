from __future__ import annotations

import json
from pathlib import Path

from dem2dsf import contracts
from dem2dsf.backends.registry import list_backends


def _load_fixture(name: str) -> dict:
    path = Path(__file__).parent / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_plan_schema() -> None:
    plan = _load_fixture("build_plan.json")
    contracts.validate_build_plan(plan)


def test_build_report_schema() -> None:
    report = _load_fixture("build_report.json")
    contracts.validate_build_report(report)


def test_build_report_schema_with_performance() -> None:
    report = _load_fixture("build_report.json")
    report["performance"] = {
        "total_seconds": 1.0,
        "spans": {"normalize": {"seconds": 0.5, "count": 1}},
        "events": [{"name": "normalize", "seconds": 0.5}],
        "peak_memory_mb": 12.5,
    }
    contracts.validate_build_report(report)


def test_runner_events_schema() -> None:
    payload = _load_fixture("runner_events.json")
    contracts.validate_runner_events(payload)


def test_backend_contracts() -> None:
    backends = list_backends()
    assert "ortho4xp" in backends
    spec = backends["ortho4xp"].spec()
    assert spec.artifact_schema_version == contracts.SCHEMA_VERSION
