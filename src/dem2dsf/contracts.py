"""Schema validation helpers for build plan, report, and runner artifacts."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Mapping

import jsonschema

SCHEMA_VERSION = "1.1"
RUNNER_EVENTS_SCHEMA_VERSION = "1"


def _load_schema(name: str) -> dict[str, Any]:
    """Load a JSON schema bundled in the package."""
    with resources.files("dem2dsf.schemas").joinpath(name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_build_plan(plan: Mapping[str, Any]) -> None:
    """Validate a build plan against the schema."""
    schema = _load_schema("build_plan.schema.json")
    jsonschema.validate(plan, schema)


def validate_build_report(report: Mapping[str, Any]) -> None:
    """Validate a build report against the schema."""
    schema = _load_schema("build_report.schema.json")
    jsonschema.validate(report, schema)


def validate_runner_events(payload: Mapping[str, Any]) -> None:
    """Validate runner event payloads against the schema."""
    schema = _load_schema("runner_events.schema.json")
    jsonschema.validate(payload, schema)
