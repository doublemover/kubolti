# Documentation

Additional project docs live here. Reference summaries are in `references/`.

Key docs:
- `../COMPLETE_PLAN.md` is the sole source of truth for roadmap and status.
- `backend_contract.md` defines the backend interface and artifact expectations.
- `pinned_versions.md` tracks toolchain versions targeted by the project.
- `dem_stack.md` documents multi-resolution DEM stack inputs.
- `patch_workflow.md` describes patch plans and patch CLI usage.
- `overlay_plugins.md` covers drape overlays and plugin generators.
- `presets.md` summarizes the built-in preset library.
- `gui.md` documents the Tkinter launcher.
- `Ortho4XP/README.md` and companions capture Ortho4XP workflow + automation notes.
- `release_signing.md` outlines release packaging and signing.
- `release_notes.md` is the draft release summary for the next tag.
- `perf_benchmarking.md` covers profiling and benchmark workflows.
- `sample_pipelines.md` lists regional build recipes and overlays.
- `references/file_formats.md`, `references/gotchas.md`, and `references/performance_tuning.md` expand on formats and tuning.
- `tool_urls.json` captures the latest XPTools URLs. Update with `python scripts/fetch_tool_urls.py --output docs/tool_urls.json` (network access required).
- `scripts/build_xptools.py` builds DSFTool/DDSTool from the pinned source tag.
