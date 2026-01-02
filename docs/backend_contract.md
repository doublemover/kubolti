# Backend Contract

Backends provide mesh generation while adhering to shared build plan/report schemas.

## Contract surface
- `BackendSpec`: name, version, tile DEM CRS, capability flags, artifact schema version.
- `build(request)`: consumes normalized tile DEMs and returns `build_plan` + `build_report` JSON objects.

## Required behaviors
- Populate `schema_version` in plan/report to match `dem2dsf.contracts.SCHEMA_VERSION`.
- Report tiles with explicit status (`ok`, `warning`, `error`, `skipped`).
- Record backend name/version used for reproducibility.

## Discovery
Backends can be discovered via package entrypoints using the group
`dem2dsf.backends`. Each entrypoint should resolve to a backend factory
(callable) or a backend class. Built-in backends are always available.

## Validation
- `dem2dsf.contracts.validate_build_plan` and `validate_build_report` are the canonical schema checks.
- Contract tests in `tests/test_contracts.py` must pass for new backends.
