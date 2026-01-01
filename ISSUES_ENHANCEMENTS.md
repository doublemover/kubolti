### 1) **Security bug: archive extraction path traversal check is bypassable**

**File:** `src/dem2dsf/tools/installer.py`
**Function:** `_safe_extract_path`

Current logic:

```py
if not str(candidate).startswith(str(root.resolve())):
    raise ValueError(...)
```

This is a classic footgun: `/tmp/root2/...` **starts with** `/tmp/root`, so a crafted archive entry like `../root2/evil` can slip through even though it escapes the intended directory.

**Fix:**
Use `Path.is_relative_to()` (py3.9+) or `relative_to()` try/except.

Example:

```py
root_resolved = root.resolve()
candidate = (root / member_path).resolve()
try:
    candidate.relative_to(root_resolved)
except ValueError:
    raise ValueError(f"Archive member escapes target directory: {member_path}")
```

**Impact:** high if you install tools from remote archives (or any untrusted source).
**Priority:** P0.

---

### 2) **NaN nodata is not filled by fill strategies**

**File:** `src/dem2dsf/dem/fill.py`
**Functions:** `fill_with_constant`, `fill_with_interpolation`, `fill_with_fallback`

These use `data == nodata`, which never matches when `nodata` is `NaN`. I verified this behavior: `filled_pixels` stays 0 with NaN nodata.

**Fix:**
Centralize a nodata mask helper (like the one in `dem/pipeline.py`) and reuse it:

```py
def _nodata_mask(data, nodata):
    if nodata is None:
        return np.zeros(data.shape, dtype=bool)
    if np.isnan(nodata):
        return np.isnan(data)
    return data == nodata
```

Then use that mask in all fill functions.

**Impact:** void-filling silently fails for NaN-nodata DEMs.
**Priority:** P0/P1 (depends on how often NaN nodata occurs in your DEM inputs).

---

### 3) **`TileResult.nodata` is wrong when `dst_nodata` is not provided**

**File:** `src/dem2dsf/dem/tiling.py`
**Function:** `write_tile_dem`

You compute:

```py
nodata = dst_nodata if dst_nodata is not None else src.nodata
...
meta.update({"nodata": nodata})
...
return TileResult(..., nodata=dst_nodata)
```

So `TileResult.nodata` becomes `None` even when the output file’s nodata is correctly set to `src.nodata`.

**Fix:**
Return `nodata`, not `dst_nodata`:

```py
return TileResult(..., nodata=nodata)
```

**Impact:** downstream logic that trusts `TileResult.nodata` will be wrong (even if today most call sites pass an explicit effective nodata).
**Priority:** P1.

---

### 4) **Ortho4XP runner config restore bug when config file didn’t previously exist**

**File:** `scripts/ortho4xp_runner.py`
**Function:** `_run_with_config`

You only restore config if `original_config is not None`:

```py
if patched and original_config is not None:
    restore_config(config_path, original_config)
```

If `Ortho4XP.cfg` **did not exist**, `patch_config_values()` likely returns `None`, and you leave behind a newly created config file with patched values.

**Fix:**
Always restore when patched; `restore_config()` already supports `None` (delete file) semantics:

```py
if patched:
    restore_config(config_path, original_config)  # original_config may be None
```

**Impact:** unexpected persistent config changes / state leaks across runs.
**Priority:** P1.

---

### 5) **GUI offers a density preset that the core doesn’t support**

**Files:**

* `src/dem2dsf/gui.py` (combobox values include `"ultra"`)
* `src/dem2dsf/density.py` (no `"ultra"`)

Selecting **ultra** in the GUI will not apply intended Ortho4XP config + triangle limits properly; it falls back to defaults.

**Fix options:**

* Add an `"ultra"` preset to `DENSITY_PRESETS` and `DENSITY_TRIANGLE_LIMITS`, or
* Remove `"ultra"` from the GUI dropdown.

**Impact:** user confusion + inconsistent behavior across CLI vs GUI.
**Priority:** P2.

---

### 6) Triangle estimation formula is slightly off

**File:** `src/dem2dsf/triangles.py`
**Function:** `estimate_triangles(width, height)`

Current: `width * height * 2`
More accurate grid triangulation is `(width - 1) * (height - 1) * 2`.

It’s a small error for large rasters, but your guardrails depend on it.

**Impact:** could trigger warnings earlier than necessary.
**Priority:** P3.

---

## Likely integration bugs (tests probably won’t catch)

These depend on real Ortho4XP/DSFTool behavior, so they won’t show up in the stubbed test environment.

### 1) XP12 enrichment probably copies `.raw` sidecars to the wrong basename

**File:** `src/dem2dsf/xp12.py`
**Function:** `enrich_dsf_rasters`

You run `DSFTool --text2dsf` using `enriched_text_path`, but you copy sidecars using:

```py
_copy_raw_sidecars(..., dest_text=target_text_path, ...)
```

If DSFTool expects sidecars named like `<input_text_filename>.*.raw`, it will look for:

* `target.enriched.txt.*.raw`

but you created:

* `target.txt.*.raw`

**Safer fix:**
Copy sidecars to match the enriched text filename:

```py
dest_text=enriched_text_path
```

Or copy to **both** to be extra safe.

**Impact:** enrichment may “work” but text2dsf could fail or produce incomplete DSFs on real DSFTool.
**Priority:** P1 (because it’s external-tool facing).

---

### 2) `target_crs` override is effectively unsupported by tiling math

Multiple functions assume the tile naming scheme `+DD+DDD` corresponds to **EPSG:4326 degrees**.

* `tile_bounds()` is always degrees.
* `write_tile_dem()` computes pixel dims from `(max_lon - min_lon)/res_x`.

If `target_crs` is projected (meters), you’ll divide degrees by meters → nonsense dimensions.

**Fix options:**

* Explicitly **disallow** non-EPSG:4326 target CRS (fail fast with a clear error), or
* Implement bounds transformation: compute tile bounds in EPSG:4326, then transform to target CRS and tile accordingly (more complex).

**Impact:** “looks like it runs” but produces wrong tiles.
**Priority:** P1/P2 depending on whether you intend to support non-4326.

---

## Performance issues and scaling concerns

### 1) Heavy redundant full-tile reads per tile

In `dem/pipeline.py`, each tile often causes multiple full reads/writes:

* `write_tile_dem()` writes file
* `_coverage_stats()` reads full band
* fill step re-opens file and reads again
* optional `apply_backend_profile()` reads & writes again
* `_coverage_stats()` reads again

**Enhancement ideas:**

* Compute “coverage before” from the array already in memory when you fill.
* When fill strategy is `none`, skip `_coverage_stats` entirely unless requested.
* When backend profile just remaps nodata, do it during write/reproject stage if possible.

**Impact:** IO bound on large tile sets.

---

### 2) `apply_backend_profile()` reads entire mosaic/tile into memory

**File:** `src/dem2dsf/dem/adapter.py`

For big mosaics, `data = src.read(1)` is a memory spike. This is especially costly if you apply the profile to the **mosaic**, not just per-tile outputs.

**Enhancement ideas:**

* Apply profile per tile, not to the full mosaic.
* Or rewrite profile mapping in blocks/windows (streaming).

---

### 3) Coverage stats reads actual DEM values (could read masks instead)

If nodata is set, you may use `dataset.read_masks(1)` or `masked=True` reads to avoid pulling full float arrays if you only need nodata counts.

---

### 4) ThreadPoolExecutor may not deliver expected speedups

In `dem/pipeline.py` tile jobs are threaded. Whether this helps depends on:

* rasterio/GDAL releasing GIL in your operations
* disk throughput
* number of concurrent reads/writes

**Enhancement ideas:**

* Make `tile_jobs` default to `min(physical_cores, tile_count)` but cap by IO bandwidth.
* Add an adaptive mode: increase workers until throughput stops improving.
* Consider `ProcessPoolExecutor` only for CPU-heavy numpy-only phases (not GDAL-heavy).

---

### 5) Capturing subprocess output in memory can explode RAM

You use `capture_output=True` in several places (runner, dsftool, 7z). If Ortho4XP or DSFTool emits huge logs, this can get expensive.

**Enhancement idea:**

* Stream stdout/stderr to file and keep only last N lines in memory for reporting.

---

### 6) Filesystem scans can be slow on real X-Plane installs

* `scan_custom_scenery()` uses `rglob("Earth nav data/*/*.dsf")`
* `scan_terrain_textures()` uses `rglob("*.ter")`

These will be slow on very large scenery setups.

**Enhancement ideas:**

* Add filters: only scan target tiles/buckets.
* Add incremental cache keyed by directory mtime and file mtimes.

---

## Comprehensive enhancement backlog

### A) Reliability & correctness

* Add explicit guardrails:

  * if `target_crs != EPSG:4326`, raise with explanation unless you fully support it
  * if `dem_paths > 1` and `normalize=False`, error out (today it silently uses the first DEM)
* Add “tile coverage hard fail” option:

  * error if coverage_before < X% rather than warning
* Add `--continue-on-error` per tile:

  * mark tile failed but continue building other tiles
* Add robust “external tool invocation” handling:

  * configurable timeouts
  * retry logic for transient failures
  * clearer mapping of stderr → actionable user messages

### B) Performance & scale

* Avoid building one huge mosaic for many tiles when possible:

  * “mosaic per tile” pipeline (only merge sources intersecting the tile)
  * or use a VRT-based mosaic and read windowed data
* Skip fallback DEM work when tile has no nodata (fast-path):

  * don’t generate fallback tiles if nodata_before == 0
* Optional “metrics mode”:

  * disable expensive coverage stats unless requested
* Add a “tile result cache”:

  * if normalized tile already exists and inputs/options unchanged, skip regeneration (you already have a normalization cache — consider partial reuse per tile)

### C) Packaging / distribution

* Move `scripts/ortho4xp_runner.py` into the package (e.g., `dem2dsf.runners.ortho4xp`) and expose it as a console script entrypoint.

  * Right now the default runner path depends on repo layout or PyInstaller layout.
* Consider lowering `requires-python` if you actually support 3.11/3.12 (your tests pass on 3.11).
* Include any needed runtime assets via `package-data` if you expect pip installs to “just work”.

### D) UX improvements (CLI + GUI)

* GUI should run builds off the main thread:

  * right now long builds will freeze the UI
* Add a progress indicator:

  * current tile / total tiles
  * current phase (normalize → build → validate → enrich)
* Add input validation early:

  * tile name format/range
  * DEM existence and readable raster
  * tool paths executable
* Reduce duplicated option wiring across CLI / wizard / GUI:

  * central `BuildOptions` dataclass + one canonical argument/field definition list
* Make presets more visible:

  * show expanded preset (what it changes) before running

### E) Observability & debugging

* Add step-level perf markers to the report:

  * warp time per DEM
  * mosaic time
  * per-tile normalize time
  * Ortho4XP runner time
  * DSFTool validation/enrichment time
* Emit a single “build bundle” artifact:

  * plan + report + per-tile logs + perf + tool versions + environment info
    (you already have diagnostics scripts; integrate into core flow optionally)

### F) Testing gaps worth filling

Add tests for the issues above that slipped through:

* NaN nodata fill strategies
* `TileResult.nodata` matches dataset nodata
* installer `_safe_extract_path` “prefix bypass” (e.g., `../root2/file`)
* xp12 enrichment sidecar naming behavior (mock DSFTool to assert the expected sidecar filenames)
* GUI density preset list matches `DENSITY_PRESETS`