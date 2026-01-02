"""Minimal Tkinter GUI for build and publish workflows."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

from dem2dsf.build import run_build
from dem2dsf.dem.stack import load_dem_stack
from dem2dsf.density import DENSITY_PRESETS
from dem2dsf.presets import get_preset, list_presets
from dem2dsf.publish import publish_build
from dem2dsf.tile_inference import infer_tiles
from dem2dsf.tools.config import load_tool_paths, ortho_root_from_paths
from dem2dsf.xplane_paths import parse_tile

ENV_GUI_PREFS = "DEM2DSF_GUI_PREFS"
GUI_PREFS_VERSION = 1


def parse_list(value: str) -> list[str]:
    """Parse comma-separated values into a list."""
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_optional_float(value: str) -> float | None:
    """Parse an optional float from a string."""
    value = value.strip()
    return float(value) if value else None


def parse_optional_int(value: str) -> int | None:
    """Parse an optional integer from a string."""
    value = value.strip()
    return int(value) if value else None


def parse_command(value: str) -> list[str] | None:
    """Parse a command string into an argv list."""
    value = value.strip()
    if not value:
        return None
    return shlex.split(value, posix=os.name != "nt")


def _invalid_tiles(tiles: list[str]) -> list[str]:
    """Return tile names that fail basic +DD+DDD validation."""
    invalid: list[str] = []
    for tile in tiles:
        try:
            parse_tile(tile)
        except ValueError:
            invalid.append(tile)
    return invalid


def default_gui_prefs_path() -> Path:
    """Return the default GUI preferences file path."""
    return Path.home() / ".dem2dsf" / "gui_prefs.json"


def _prefs_candidates(explicit_path: Path | None) -> list[Path]:
    """Return candidate preference file locations in priority order."""
    candidates: list[Path] = []
    env_path = os.environ.get(ENV_GUI_PREFS)
    if env_path:
        candidates.append(Path(env_path))
    if explicit_path:
        candidates.append(explicit_path)
    candidates.append(default_gui_prefs_path())
    return candidates


def _normalize_prefs(payload: Any) -> dict[str, dict[str, Any]]:
    """Normalize a preference payload into build/publish mappings."""
    if not isinstance(payload, dict):
        return {"build": {}, "publish": {}}
    build = payload.get("build")
    publish = payload.get("publish")
    return {
        "build": build if isinstance(build, dict) else {},
        "publish": publish if isinstance(publish, dict) else {},
    }


def load_gui_prefs(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load GUI preferences from disk, if available."""
    for candidate in _prefs_candidates(path):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        return _normalize_prefs(payload)
    return {"build": {}, "publish": {}}


def save_gui_prefs(payload: dict[str, dict[str, Any]], path: Path | None = None) -> Path:
    """Persist GUI preferences to disk and return the path."""
    output_path = (
        Path(os.environ.get(ENV_GUI_PREFS))
        if os.environ.get(ENV_GUI_PREFS)
        else (path or default_gui_prefs_path())
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = {
        "version": GUI_PREFS_VERSION,
        "build": payload.get("build", {}),
        "publish": payload.get("publish", {}),
    }
    output_path.write_text(json.dumps(wrapped, indent=2), encoding="utf-8")
    return output_path


def _apply_prefs(
    variables: dict[str, Any],
    prefs: dict[str, Any],
) -> None:
    """Apply preference values to Tk variables."""
    for key, var in variables.items():
        if key not in prefs:
            continue
        value = prefs.get(key)
        if value is None:
            continue
        var.set(value)


def _collect_prefs(
    build_vars: dict[str, Any],
    publish_vars: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Collect preferences from Tk variables."""
    return {
        "build": {key: var.get() for key, var in build_vars.items()},
        "publish": {key: var.get() for key, var in publish_vars.items()},
    }


def _default_ortho_runner() -> list[str] | None:
    """Return a command for the bundled Ortho4XP runner if available."""
    if hasattr(sys, "_MEIPASS"):
        candidate = Path(getattr(sys, "_MEIPASS")) / "scripts" / "ortho4xp_runner.py"
        if candidate.exists():
            return [sys.executable, str(candidate)]
    runner = Path(__file__).resolve().parents[2] / "scripts" / "ortho4xp_runner.py"
    if runner.exists():
        return [sys.executable, str(runner)]
    console = shutil.which("dem2dsf-ortho4xp")
    if console:
        return [console]
    return [sys.executable, "-m", "dem2dsf.runners.ortho4xp"]


def _apply_tool_defaults(
    options: dict[str, Any],
    *,
    ortho_root: str | None,
    dsftool_path: str | None,
    ddstool_path: str | None,
) -> None:
    """Fill tool defaults from tool_paths.json when GUI fields are empty."""
    tool_paths = load_tool_paths()
    if options.get("runner") is None:
        ortho_root_path = Path(ortho_root) if ortho_root else ortho_root_from_paths(tool_paths)
        runner = _default_ortho_runner()
        if ortho_root_path and runner:
            options["runner"] = [*runner, "--ortho-root", str(ortho_root_path)]
    if options.get("dsftool") is None:
        candidate = Path(dsftool_path) if dsftool_path else tool_paths.get("dsftool")
        if candidate:
            options["dsftool"] = [str(candidate)]
    if options.get("ddstool") is None:
        candidate = Path(ddstool_path) if ddstool_path else tool_paths.get("ddstool")
        if candidate:
            options["ddstool"] = [str(candidate)]


def _runner_has_flag(runner: list[str], flag: str) -> bool:
    for token in runner:
        if token == flag or token.startswith(f"{flag}="):
            return True
    return False


def _apply_runner_overrides(
    options: dict[str, Any],
    *,
    ortho_root: str | None,
    ortho_python: str | None,
    ortho_batch: bool,
    persist_config: bool,
) -> None:
    runner = options.get("runner")
    if not runner:
        return
    if ortho_root and not _runner_has_flag(runner, "--ortho-root"):
        runner.extend(["--ortho-root", str(ortho_root)])
    if ortho_python and not _runner_has_flag(runner, "--python"):
        runner.extend(["--python", ortho_python])
    if ortho_batch and "--batch" not in runner:
        runner.append("--batch")
    if persist_config and not _runner_has_flag(runner, "--persist-config"):
        runner.append("--persist-config")


def build_form_to_request(
    values: dict[str, Any],
) -> tuple[list[Path], list[str], Path, dict[str, Any]]:
    """Convert GUI form values into a build request."""
    dem_paths = [Path(path) for path in parse_list(values.get("dems", ""))]
    dem_stack = values.get("dem_stack") or ""
    tiles = parse_list(values.get("tiles", ""))
    output_dir = Path(values.get("output_dir") or "build")
    options = {
        "quality": values.get("quality", "compat"),
        "density": values.get("density", "medium"),
        "autoortho": bool(values.get("autoortho", False)),
        "autoortho_texture_strict": bool(values.get("autoortho_texture_strict", False)),
        "aoi": values.get("aoi_path") or None,
        "aoi_crs": values.get("aoi_crs") or None,
        "infer_tiles": bool(values.get("infer_tiles", False)),
        "target_crs": values.get("target_crs") or "EPSG:4326",
        "resampling": values.get("resampling", "bilinear"),
        "target_resolution": parse_optional_float(values.get("target_resolution", "")),
        "dst_nodata": parse_optional_float(values.get("dst_nodata", "")),
        "fill_strategy": values.get("fill_strategy", "none"),
        "fill_value": parse_optional_float(values.get("fill_value", "") or "0") or 0.0,
        "fallback_dem_paths": parse_list(values.get("fallback_dems", "")),
        "normalize": not bool(values.get("skip_normalize", False)),
        "tile_jobs": parse_optional_int(values.get("tile_jobs", "") or "1") or 1,
        "triangle_warn": parse_optional_int(values.get("triangle_warn", "")),
        "triangle_max": parse_optional_int(values.get("triangle_max", "")),
        "allow_triangle_overage": bool(values.get("allow_triangle_overage", False)),
        "global_scenery": values.get("global_scenery") or None,
        "enrich_xp12": bool(values.get("enrich_xp12", False)),
        "xp12_strict": bool(values.get("xp12_strict", False)),
        "profile": bool(values.get("profile", False)),
        "metrics_json": values.get("metrics_json") or None,
        "dem_stack_path": dem_stack or None,
        "dry_run": bool(values.get("dry_run", False)),
        "mosaic_strategy": values.get("mosaic_strategy") or "full",
        "continue_on_error": bool(values.get("continue_on_error", False)),
        "coverage_min": parse_optional_float(values.get("coverage_min", "")),
        "coverage_hard_fail": bool(values.get("coverage_hard_fail", False)),
        "coverage_metrics": bool(values.get("coverage_metrics", True)),
        "runner_timeout": parse_optional_float(values.get("runner_timeout", "")),
        "runner_retries": parse_optional_int(values.get("runner_retries", "") or "0") or 0,
        "runner_stream_logs": bool(values.get("runner_stream_logs", False)),
        "dsftool_timeout": parse_optional_float(values.get("dsftool_timeout", "")),
        "dsftool_retries": parse_optional_int(values.get("dsftool_retries", "") or "0") or 0,
        "dsf_validation": values.get("dsf_validation") or "roundtrip",
        "dsf_validation_workers": parse_optional_int(values.get("dsf_validation_workers", "")),
        "validate_all": bool(values.get("validate_all", False)),
        "dds_validation": values.get("dds_validation") or "none",
        "dds_strict": bool(values.get("dds_strict", False)),
        "bundle_diagnostics": bool(values.get("bundle_diagnostics", False)),
    }
    ortho_root = values.get("ortho_root") or None
    ortho_python = values.get("ortho_python") or None
    ortho_batch = bool(values.get("ortho_batch", False))
    persist_config = bool(values.get("persist_config", False))
    dsftool_path = values.get("dsftool_path") or None
    ddstool_path = values.get("ddstool_path") or None
    runner_override = parse_command(values.get("runner_cmd", ""))
    if runner_override:
        options["runner"] = runner_override
    if ortho_root and "runner" not in options:
        runner = _default_ortho_runner()
        if runner:
            options["runner"] = [*runner, "--ortho-root", str(ortho_root)]
    if dsftool_path:
        options["dsftool"] = [dsftool_path]
    if ddstool_path:
        options["ddstool"] = [ddstool_path]
    _apply_tool_defaults(
        options,
        ortho_root=ortho_root,
        dsftool_path=dsftool_path,
        ddstool_path=ddstool_path,
    )
    _apply_runner_overrides(
        options,
        ortho_root=ortho_root,
        ortho_python=ortho_python,
        ortho_batch=ortho_batch,
        persist_config=persist_config,
    )
    return dem_paths, tiles, output_dir, options


def publish_form_to_request(
    values: dict[str, Any],
) -> tuple[Path, Path, dict[str, Any]]:
    """Convert GUI form values into a publish request."""
    build_dir = Path(values.get("build_dir") or "build")
    output_zip = Path(values.get("output_zip") or "build.zip")
    sevenzip = values.get("sevenzip_path")
    options = {
        "mode": values.get("mode") or "full",
        "dsf_7z": bool(values.get("dsf_7z", False)),
        "dsf_7z_backup": bool(values.get("dsf_7z_backup", False)),
        "sevenzip_path": Path(sevenzip) if sevenzip else None,
        "allow_missing_sevenzip": bool(values.get("allow_missing_7z", False)),
    }
    return build_dir, output_zip, options


def launch_gui() -> None:
    """Launch the Tkinter GUI."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:  # pragma: no cover - depends on system tk install
        raise RuntimeError("tkinter is required for the GUI.") from exc

    root = tk.Tk()
    root.title("DEM2DSF Launcher")
    notebook = ttk.Notebook(root)

    build_frame = ttk.Frame(notebook)
    publish_frame = ttk.Frame(notebook)
    notebook.add(build_frame, text="Wizard")
    notebook.add(publish_frame, text="Publish")
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    build_vars = {
        "preset": tk.StringVar(),
        "dems": tk.StringVar(),
        "dem_stack": tk.StringVar(),
        "aoi_path": tk.StringVar(),
        "aoi_crs": tk.StringVar(),
        "tiles": tk.StringVar(),
        "infer_tiles": tk.BooleanVar(value=False),
        "output_dir": tk.StringVar(value="build"),
        "quality": tk.StringVar(value="compat"),
        "density": tk.StringVar(value="medium"),
        "autoortho": tk.BooleanVar(value=False),
        "autoortho_texture_strict": tk.BooleanVar(value=False),
        "skip_normalize": tk.BooleanVar(value=False),
        "tile_jobs": tk.StringVar(value="1"),
        "triangle_warn": tk.StringVar(),
        "triangle_max": tk.StringVar(),
        "allow_triangle_overage": tk.BooleanVar(value=False),
        "runner_cmd": tk.StringVar(),
        "ortho_root": tk.StringVar(),
        "ortho_python": tk.StringVar(),
        "ortho_batch": tk.BooleanVar(value=False),
        "dsftool_path": tk.StringVar(),
        "ddstool_path": tk.StringVar(),
        "dsf_validation": tk.StringVar(value="roundtrip"),
        "dsf_validation_workers": tk.StringVar(),
        "validate_all": tk.BooleanVar(value=False),
        "dds_validation": tk.StringVar(value="none"),
        "dds_strict": tk.BooleanVar(value=False),
        "target_crs": tk.StringVar(value="EPSG:4326"),
        "resampling": tk.StringVar(value="bilinear"),
        "target_resolution": tk.StringVar(),
        "dst_nodata": tk.StringVar(),
        "fill_strategy": tk.StringVar(value="none"),
        "fill_value": tk.StringVar(value="0"),
        "fallback_dems": tk.StringVar(),
        "global_scenery": tk.StringVar(),
        "enrich_xp12": tk.BooleanVar(value=False),
        "xp12_strict": tk.BooleanVar(value=False),
        "profile": tk.BooleanVar(value=False),
        "metrics_json": tk.StringVar(),
        "dry_run": tk.BooleanVar(value=False),
        "mosaic_strategy": tk.StringVar(value="full"),
        "continue_on_error": tk.BooleanVar(value=False),
        "coverage_min": tk.StringVar(),
        "coverage_hard_fail": tk.BooleanVar(value=False),
        "coverage_metrics": tk.BooleanVar(value=True),
        "runner_timeout": tk.StringVar(),
        "runner_retries": tk.StringVar(value="0"),
        "runner_stream_logs": tk.BooleanVar(value=False),
        "persist_config": tk.BooleanVar(value=False),
        "dsftool_timeout": tk.StringVar(),
        "dsftool_retries": tk.StringVar(value="0"),
        "bundle_diagnostics": tk.BooleanVar(value=False),
    }

    publish_vars = {
        "build_dir": tk.StringVar(value="build"),
        "output_zip": tk.StringVar(value="build.zip"),
        "mode": tk.StringVar(value="full"),
        "dsf_7z": tk.BooleanVar(value=False),
        "dsf_7z_backup": tk.BooleanVar(value=False),
        "sevenzip_path": tk.StringVar(),
        "allow_missing_7z": tk.BooleanVar(value=False),
    }
    prefs = load_gui_prefs()
    _apply_prefs(build_vars, prefs.get("build", {}))
    _apply_prefs(publish_vars, prefs.get("publish", {}))

    def log_message(text: str) -> None:
        log.insert("end", text + "\n")
        log.see("end")

    def save_preferences() -> None:
        try:
            save_gui_prefs(_collect_prefs(build_vars, publish_vars))
        except (OSError, ValueError, TypeError):
            log_message("Failed to save GUI preferences.")

    def apply_preset() -> None:
        preset_name = build_vars["preset"].get()
        preset = get_preset(preset_name or "")
        if not preset:
            messagebox.showerror("Unknown preset", f"Preset not found: {preset_name}")
            return
        for key, value in preset.options.items():
            if key in build_vars:
                build_vars[key].set(str(value))
        log_message(f"Applied preset: {preset.name}")

    def browse_dems() -> None:
        paths = filedialog.askopenfilenames(title="Select DEM files")
        if paths:
            build_vars["dems"].set(", ".join(paths))

    def browse_dem_stack() -> None:
        path = filedialog.askopenfilename(
            title="Select DEM stack JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            build_vars["dem_stack"].set(path)

    def browse_aoi() -> None:
        path = filedialog.askopenfilename(
            title="Select AOI polygon",
            filetypes=[
                ("GeoJSON", "*.json;*.geojson"),
                ("Shapefile", "*.shp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            build_vars["aoi_path"].set(path)

    def browse_output_dir() -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            build_vars["output_dir"].set(path)

    def browse_ortho_root() -> None:
        path = filedialog.askdirectory(title="Select Ortho4XP root")
        if path:
            build_vars["ortho_root"].set(path)

    def browse_ortho_python() -> None:
        path = filedialog.askopenfilename(title="Select Ortho4XP Python executable")
        if path:
            build_vars["ortho_python"].set(path)

    def browse_dsftool() -> None:
        path = filedialog.askopenfilename(title="Select DSFTool executable")
        if path:
            build_vars["dsftool_path"].set(path)

    def browse_ddstool() -> None:
        path = filedialog.askopenfilename(title="Select DDSTool executable")
        if path:
            build_vars["ddstool_path"].set(path)

    def browse_fallback() -> None:
        paths = filedialog.askopenfilenames(title="Select fallback DEMs")
        if paths:
            build_vars["fallback_dems"].set(", ".join(paths))

    def browse_global_scenery() -> None:
        path = filedialog.askdirectory(title="Select Global Scenery folder")
        if path:
            build_vars["global_scenery"].set(path)

    def browse_metrics_json() -> None:
        path = filedialog.asksaveasfilename(
            title="Save metrics JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            build_vars["metrics_json"].set(path)

    def _infer_tiles_for_values(values: dict[str, Any]):
        dem_paths = [Path(path) for path in parse_list(values.get("dems", ""))]
        dem_stack = values.get("dem_stack") or ""
        if not dem_paths and dem_stack:
            stack = load_dem_stack(Path(dem_stack))
            dem_paths = [layer.path for layer in stack.layers]
        if not dem_paths:
            raise ValueError("Provide DEMs or a DEM stack to infer tiles.")
        aoi_path = values.get("aoi_path") or None
        aoi_crs = values.get("aoi_crs") or None
        return infer_tiles(
            dem_paths,
            aoi_path=Path(aoi_path) if aoi_path else None,
            aoi_crs=aoi_crs or None,
        )

    def on_infer_tiles() -> None:
        values = {key: var.get() for key, var in build_vars.items()}
        try:
            inference = _infer_tiles_for_values(values)
        except Exception as exc:
            messagebox.showerror("Tile inference failed", str(exc))
            return
        if inference.warnings:
            for warning in inference.warnings:
                log_message(f"Warning: {warning}")
        build_vars["tiles"].set(", ".join(inference.tiles))
        log_message(f"Inferred {len(inference.tiles)} tile(s).")

    def on_build() -> None:
        values = {key: var.get() for key, var in build_vars.items()}
        try:
            dem_paths, tiles, output_dir, options = build_form_to_request(values)
            if not dem_paths and not options.get("dem_stack_path"):
                messagebox.showerror("Missing input", "Provide DEMs or a DEM stack.")
                return
            if not tiles and options.get("infer_tiles"):
                inference = _infer_tiles_for_values(values)
                if inference.warnings:
                    for warning in inference.warnings:
                        log_message(f"Warning: {warning}")
                tiles = inference.tiles
                build_vars["tiles"].set(", ".join(tiles))
            if not tiles:
                messagebox.showerror(
                    "Missing input",
                    "Provide tile names or enable tile inference.",
                )
                return
            invalid_tiles = _invalid_tiles(tiles)
            if invalid_tiles:
                messagebox.showerror(
                    "Invalid tiles",
                    f"Invalid tile name(s): {', '.join(invalid_tiles)}",
                )
                return
            run_build(
                dem_paths=dem_paths,
                tiles=tiles,
                backend_name="ortho4xp",
                output_dir=output_dir,
                options=options,
            )
            save_preferences()
            log_message(f"Build complete: {output_dir}")
        except Exception as exc:
            messagebox.showerror("Build failed", str(exc))

    def on_publish() -> None:
        values = {key: var.get() for key, var in publish_vars.items()}
        try:
            build_dir, output_zip, options = publish_form_to_request(values)
            result = publish_build(
                build_dir,
                output_zip,
                dsf_7z=options["dsf_7z"],
                dsf_7z_backup=options["dsf_7z_backup"],
                sevenzip_path=options["sevenzip_path"],
                allow_missing_sevenzip=options["allow_missing_sevenzip"],
            )
            save_preferences()
            log_message(f"Published: {result['zip_path']}")
        except Exception as exc:
            messagebox.showerror("Publish failed", str(exc))

    def add_row(parent, label, widget, row) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        widget.grid(row=row, column=1, sticky="ew", padx=4, pady=4)

    def add_row_with_button(parent, label, widget, row, button) -> None:
        add_row(parent, label, widget, row)
        button.grid(row=row, column=2, sticky="e", padx=4, pady=4)

    build_frame.columnconfigure(1, weight=1)
    preset_names = [preset.name for preset in list_presets()]
    if preset_names:
        build_vars["preset"].set(preset_names[0])
    row = 0
    preset_box = ttk.Combobox(
        build_frame,
        textvariable=build_vars["preset"],
        values=preset_names,
    )
    add_row_with_button(
        build_frame,
        "Preset",
        preset_box,
        row,
        ttk.Button(build_frame, text="Apply", command=apply_preset),
    )
    row += 1
    dem_entry = ttk.Entry(build_frame, textvariable=build_vars["dems"])
    add_row_with_button(
        build_frame,
        "DEMs (comma-separated)",
        dem_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_dems),
    )
    row += 1
    dem_stack_entry = ttk.Entry(build_frame, textvariable=build_vars["dem_stack"])
    add_row_with_button(
        build_frame,
        "DEM stack (optional)",
        dem_stack_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_dem_stack),
    )
    row += 1
    aoi_entry = ttk.Entry(build_frame, textvariable=build_vars["aoi_path"])
    add_row_with_button(
        build_frame,
        "AOI polygon (optional)",
        aoi_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_aoi),
    )
    row += 1
    aoi_crs_entry = ttk.Entry(build_frame, textvariable=build_vars["aoi_crs"])
    add_row(
        build_frame,
        "AOI CRS (optional, preferred: EPSG:4326)",
        aoi_crs_entry,
        row,
    )
    row += 1
    tiles_entry = ttk.Entry(build_frame, textvariable=build_vars["tiles"])
    add_row_with_button(
        build_frame,
        "Tiles (comma-separated)",
        tiles_entry,
        row,
        ttk.Button(build_frame, text="Infer", command=on_infer_tiles),
    )
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Infer tiles from DEM/AOI when empty",
        variable=build_vars["infer_tiles"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    output_entry = ttk.Entry(build_frame, textvariable=build_vars["output_dir"])
    add_row_with_button(
        build_frame,
        "Output dir",
        output_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_output_dir),
    )
    row += 1
    quality_box = ttk.Combobox(
        build_frame,
        textvariable=build_vars["quality"],
        values=["compat", "xp12-enhanced"],
    )
    add_row(build_frame, "Quality", quality_box, row)
    row += 1
    density_box = ttk.Combobox(
        build_frame,
        textvariable=build_vars["density"],
        values=list(DENSITY_PRESETS.keys()),
    )
    add_row(build_frame, "Density", density_box, row)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="AutoOrtho mode (skip downloads)",
        variable=build_vars["autoortho"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="AutoOrtho textures strict",
        variable=build_vars["autoortho_texture_strict"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Skip normalization",
        variable=build_vars["skip_normalize"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    mosaic_box = ttk.Combobox(
        build_frame,
        textvariable=build_vars["mosaic_strategy"],
        values=["full", "per-tile"],
    )
    add_row(build_frame, "Mosaic strategy", mosaic_box, row)
    row += 1
    tile_jobs_entry = ttk.Entry(build_frame, textvariable=build_vars["tile_jobs"])
    add_row(build_frame, "Tile workers", tile_jobs_entry, row)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Continue on error",
        variable=build_vars["continue_on_error"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    coverage_min_entry = ttk.Entry(build_frame, textvariable=build_vars["coverage_min"])
    add_row(build_frame, "Min coverage (0-1)", coverage_min_entry, row)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Coverage hard fail",
        variable=build_vars["coverage_hard_fail"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Collect coverage metrics",
        variable=build_vars["coverage_metrics"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    triangle_warn_entry = ttk.Entry(build_frame, textvariable=build_vars["triangle_warn"])
    add_row(build_frame, "Triangle warn threshold", triangle_warn_entry, row)
    row += 1
    triangle_max_entry = ttk.Entry(build_frame, textvariable=build_vars["triangle_max"])
    add_row(build_frame, "Triangle max threshold", triangle_max_entry, row)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Allow triangle overage",
        variable=build_vars["allow_triangle_overage"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    runner_entry = ttk.Entry(build_frame, textvariable=build_vars["runner_cmd"])
    add_row(build_frame, "Runner override", runner_entry, row)
    row += 1
    runner_timeout_entry = ttk.Entry(build_frame, textvariable=build_vars["runner_timeout"])
    add_row(build_frame, "Runner timeout (s)", runner_timeout_entry, row)
    row += 1
    runner_retries_entry = ttk.Entry(build_frame, textvariable=build_vars["runner_retries"])
    add_row(build_frame, "Runner retries", runner_retries_entry, row)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Stream runner logs",
        variable=build_vars["runner_stream_logs"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Persist Ortho4XP.cfg",
        variable=build_vars["persist_config"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    ortho_entry = ttk.Entry(build_frame, textvariable=build_vars["ortho_root"])
    add_row_with_button(
        build_frame,
        "Ortho4XP root",
        ortho_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_ortho_root),
    )
    row += 1
    ortho_python_entry = ttk.Entry(build_frame, textvariable=build_vars["ortho_python"])
    add_row_with_button(
        build_frame,
        "Ortho4XP python",
        ortho_python_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_ortho_python),
    )
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Ortho4XP batch mode",
        variable=build_vars["ortho_batch"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    dsftool_entry = ttk.Entry(build_frame, textvariable=build_vars["dsftool_path"])
    add_row_with_button(
        build_frame,
        "DSFTool path",
        dsftool_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_dsftool),
    )
    row += 1
    ddstool_entry = ttk.Entry(build_frame, textvariable=build_vars["ddstool_path"])
    add_row_with_button(
        build_frame,
        "DDSTool path",
        ddstool_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_ddstool),
    )
    row += 1
    dsftool_timeout_entry = ttk.Entry(build_frame, textvariable=build_vars["dsftool_timeout"])
    add_row(build_frame, "DSFTool timeout (s)", dsftool_timeout_entry, row)
    row += 1
    dsftool_retries_entry = ttk.Entry(build_frame, textvariable=build_vars["dsftool_retries"])
    add_row(build_frame, "DSFTool retries", dsftool_retries_entry, row)
    row += 1
    dsf_validation_box = ttk.Combobox(
        build_frame,
        textvariable=build_vars["dsf_validation"],
        values=["roundtrip", "bounds", "none"],
    )
    add_row(build_frame, "DSF validation", dsf_validation_box, row)
    row += 1
    dsf_workers_entry = ttk.Entry(build_frame, textvariable=build_vars["dsf_validation_workers"])
    add_row(build_frame, "DSF validation workers", dsf_workers_entry, row)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Validate all tiles",
        variable=build_vars["validate_all"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    dds_validation_box = ttk.Combobox(
        build_frame,
        textvariable=build_vars["dds_validation"],
        values=["none", "header", "ddstool"],
    )
    add_row(build_frame, "DDS validation", dds_validation_box, row)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="DDS validation strict",
        variable=build_vars["dds_strict"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    target_crs_entry = ttk.Entry(build_frame, textvariable=build_vars["target_crs"])
    add_row(build_frame, "Target CRS", target_crs_entry, row)
    row += 1
    resampling_box = ttk.Combobox(
        build_frame,
        textvariable=build_vars["resampling"],
        values=["nearest", "bilinear", "cubic", "average"],
    )
    add_row(build_frame, "Resampling", resampling_box, row)
    row += 1
    target_res_entry = ttk.Entry(build_frame, textvariable=build_vars["target_resolution"])
    add_row(build_frame, "Target resolution (m)", target_res_entry, row)
    row += 1
    dst_nodata_entry = ttk.Entry(build_frame, textvariable=build_vars["dst_nodata"])
    add_row(build_frame, "Destination nodata", dst_nodata_entry, row)
    row += 1
    fill_box = ttk.Combobox(
        build_frame,
        textvariable=build_vars["fill_strategy"],
        values=["none", "constant", "interpolate", "fallback"],
    )
    add_row(build_frame, "Fill strategy", fill_box, row)
    row += 1
    fill_value_entry = ttk.Entry(build_frame, textvariable=build_vars["fill_value"])
    add_row(build_frame, "Fill value", fill_value_entry, row)
    row += 1
    fallback_entry = ttk.Entry(build_frame, textvariable=build_vars["fallback_dems"])
    add_row_with_button(
        build_frame,
        "Fallback DEMs",
        fallback_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_fallback),
    )
    row += 1
    global_entry = ttk.Entry(build_frame, textvariable=build_vars["global_scenery"])
    add_row_with_button(
        build_frame,
        "Global Scenery",
        global_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_global_scenery),
    )
    row += 1
    ttk.Checkbutton(
        build_frame, text="Enrich XP12 rasters", variable=build_vars["enrich_xp12"]
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="XP12 raster strict",
        variable=build_vars["xp12_strict"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    ttk.Checkbutton(build_frame, text="Profile build", variable=build_vars["profile"]).grid(
        row=row, column=1, sticky="w", padx=4, pady=4
    )
    row += 1
    metrics_entry = ttk.Entry(build_frame, textvariable=build_vars["metrics_json"])
    add_row_with_button(
        build_frame,
        "Metrics JSON",
        metrics_entry,
        row,
        ttk.Button(build_frame, text="Browse", command=browse_metrics_json),
    )
    row += 1
    ttk.Checkbutton(
        build_frame,
        text="Bundle diagnostics",
        variable=build_vars["bundle_diagnostics"],
    ).grid(row=row, column=1, sticky="w", padx=4, pady=4)
    row += 1
    ttk.Checkbutton(build_frame, text="Dry run", variable=build_vars["dry_run"]).grid(
        row=row, column=1, sticky="w", padx=4, pady=4
    )
    row += 1
    ttk.Button(build_frame, text="Run Build", command=on_build).grid(
        row=row, column=1, sticky="e", padx=4, pady=8
    )

    publish_frame.columnconfigure(1, weight=1)
    build_dir_entry = ttk.Entry(publish_frame, textvariable=publish_vars["build_dir"])
    output_zip_entry = ttk.Entry(publish_frame, textvariable=publish_vars["output_zip"])
    sevenzip_entry = ttk.Entry(publish_frame, textvariable=publish_vars["sevenzip_path"])
    add_row_with_button(
        publish_frame,
        "Build dir",
        build_dir_entry,
        0,
        ttk.Button(
            publish_frame,
            text="Browse",
            command=lambda: publish_vars["build_dir"].set(
                filedialog.askdirectory(title="Select build directory")
                or publish_vars["build_dir"].get()
            ),
        ),
    )
    add_row_with_button(
        publish_frame,
        "Output zip",
        output_zip_entry,
        1,
        ttk.Button(
            publish_frame,
            text="Browse",
            command=lambda: publish_vars["output_zip"].set(
                filedialog.asksaveasfilename(
                    title="Save zip file",
                    defaultextension=".zip",
                    filetypes=[("Zip files", "*.zip"), ("All files", "*.*")],
                )
                or publish_vars["output_zip"].get()
            ),
        ),
    )
    mode_box = ttk.Combobox(
        publish_frame,
        textvariable=publish_vars["mode"],
        values=["full", "scenery"],
    )
    add_row(publish_frame, "Publish mode", mode_box, 2)
    add_row_with_button(
        publish_frame,
        "7z path",
        sevenzip_entry,
        3,
        ttk.Button(
            publish_frame,
            text="Browse",
            command=lambda: publish_vars["sevenzip_path"].set(
                filedialog.askopenfilename(title="Select 7z executable")
                or publish_vars["sevenzip_path"].get()
            ),
        ),
    )
    ttk.Checkbutton(
        publish_frame,
        text="Compress DSFs (7z)",
        variable=publish_vars["dsf_7z"],
    ).grid(row=4, column=1, sticky="w", padx=4, pady=4)
    ttk.Checkbutton(
        publish_frame,
        text="Keep uncompressed DSF backups",
        variable=publish_vars["dsf_7z_backup"],
    ).grid(row=5, column=1, sticky="w", padx=4, pady=4)
    ttk.Checkbutton(
        publish_frame,
        text="Allow missing 7z",
        variable=publish_vars["allow_missing_7z"],
    ).grid(row=6, column=1, sticky="w", padx=4, pady=4)
    ttk.Button(publish_frame, text="Publish", command=on_publish).grid(
        row=7, column=1, sticky="e", padx=4, pady=8
    )

    log = tk.Text(root, height=6, width=80)
    log.pack(fill="both", expand=False, padx=10, pady=10)

    def on_close() -> None:
        save_preferences()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


def main() -> int:
    """Entry point for `python -m dem2dsf.gui`."""
    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
