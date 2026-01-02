# Migrations

## Build plan/report schema 1.2
- `created_at` is optional; use `--stable-metadata` to omit it for deterministic metadata.
- A new `provenance` block captures input fingerprints, toolchain details, environment versions, coverage summary, and pinned-version drift.
- Update any downstream validators to allow the new fields and optional timestamps.
