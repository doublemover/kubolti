# Repository Guidelines

## Project Structure & Module Organization
- `src/dem2dsf/` contains the CLI, build pipeline, and validation helpers.
- `tests/` holds pytest coverage for normalization, backends, XP12 checks, and AutoOrtho validation.
- `scripts/` includes `install_dev.py` and `ortho4xp_runner.py`.
- `docs/` stores specs and reference summaries; `docs/references/` contains external notes.
- `assets/` is reserved for example data and media.

## Build, Test, and Development Commands
- `python scripts/install_dev.py` bootstraps the `.venv` and installs dev deps.
- `python -m dem2dsf --help` lists CLI commands.
- `python -m dem2dsf build --dem <file> --tile +DD+DDD --runner <cmd...>` builds tiles (runner required).
- `python -m dem2dsf build --quality xp12-enhanced --dsftool <path> --global-scenery <dir> --enrich-xp12` enables XP12 raster checks + enrichment.
- `python -m dem2dsf doctor --runner <cmd...> --dsftool <path>` checks tool availability.
- `python -m dem2dsf autoortho --dem <file> --tile +DD+DDD --ortho-root <dir>` runs the AutoOrtho preset build.
- `python -m dem2dsf scan --scenery-root <Custom Scenery>` reports tile conflicts.
- `python -m dem2dsf publish --build-dir build --output build.zip` creates a zip + manifest.
- `pytest` runs unit tests; `pytest --cov=dem2dsf --cov-report=term-missing` reports coverage.
- `ruff check .` runs lint.

## Feature Status (Trail Map)
- [x] DEM normalization (mosaic, reprojection, tiling, nodata handling).
- [x] Ortho4XP runner hook + density mapping.
- [x] Wizard/doctor scaffolding.
- [x] XP12 raster inventory + triangle guardrails.
- [x] AutoOrtho validator + runner support for skip_downloads.
- [x] Tile conflict detector + publish step.
- [x] Raster enrichment merge (Global Scenery).

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints where helpful, ruff for lint.
- Files: lowercase with underscores, version suffixes for specs.
- Keep CLI flags kebab-case (for example, `--max-triangles`, `--global-scenery`).

## Testing Guidelines
- Add unit tests alongside new modules in `tests/`.
- Prefer fast fixtures (temp dirs) and stub runners for backend tests.
- Keep DSF tooling tests isolated; use tiny stub scripts.

## Dependencies & Configuration Notes
- Target runtime: Python 3.13.
- XP12 raster checks/enrichment require `DSFTool` (`--dsftool`) and `--global-scenery`.
- Ortho4XP is BYO; `scripts/ortho4xp_runner.py` expects `--ortho-root` and stages `Elevation_data`.
- Scenery scans expect an X-Plane Custom Scenery root with `scenery_packs.ini`.
- AutoOrtho expects texture names like `row_col_maptype_zl.dds` and skip_downloads in Ortho4XP config.

## Commit & Pull Request Guidelines
Commit messages should be useful with a light, non-cringe flavor tag:
`<area>: <imperative summary> (<terrain tag>)` for example `docs: add DSF reference notes (ridge)`.
Keep summaries under 72 characters; use tags like `tile`, `mesh`, `raster`, `warp`.
PRs should include a summary, verification notes (even if "docs only"), and links to backlog items when applicable.
