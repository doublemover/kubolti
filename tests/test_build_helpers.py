from __future__ import annotations

from pathlib import Path

import pytest

from dem2dsf import build
from dem2dsf.autoortho import AutoOrthoReport
from dem2dsf.backends.base import BackendSpec, BuildRequest, BuildResult
from dem2dsf.dem.models import CoverageMetrics, TileResult
from dem2dsf.dem.pipeline import NormalizationResult
from dem2dsf.dem.stack import DemLayer, DemStack
from dem2dsf.xp12 import EnrichmentResult, RasterSummary
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path


class DummyBackend:
    def __init__(self) -> None:
        self._spec = BackendSpec(
            name="dummy",
            version="0",
            artifact_schema_version="1.2",
            tile_dem_crs="EPSG:4326",
            supports_xp12_rasters=True,
            supports_autoortho=True,
        )

    def spec(self) -> BackendSpec:
        return self._spec

    def build(self, request: BuildRequest) -> BuildResult:
        return BuildResult(build_plan={}, build_report={"tiles": [], "warnings": [], "errors": []})


def test_normalize_command_variants() -> None:
    assert build._normalize_command(None) is None
    assert build._normalize_command(["tool", 1]) == ["tool", "1"]
    assert build._normalize_command("tool") == ["tool"]
    with pytest.raises(TypeError, match="Command must be"):
        build._normalize_command(123)


def test_resolve_tool_command() -> None:
    assert build._resolve_tool_command(None) is None
    assert build._resolve_tool_command(["/tmp/tool"]) == ["/tmp/tool"]


def test_validate_build_inputs_allows_tile_dem_paths(tmp_path: Path) -> None:
    tile = "+47+008"
    tile_path = tmp_path / "tile.tif"
    tile_path.write_text("dem", encoding="utf-8")

    build._validate_build_inputs(
        tiles=[tile],
        dem_paths=[tmp_path / "a.tif", tmp_path / "b.tif"],
        options={
            "normalize": False,
            "tile_dem_paths": {tile: str(tile_path)},
            "dem_stack_path": str(tmp_path / "stack.json"),
            "dry_run": True,
        },
    )


def test_message_and_metric_helpers() -> None:
    tile_entry = {"status": "ok"}
    messages = build._ensure_messages(tile_entry)
    metrics = build._ensure_metrics(tile_entry)

    assert messages == []
    assert metrics == {}
    build._mark_warning(tile_entry)
    assert tile_entry["status"] == "warning"
    build._mark_error(tile_entry)
    assert tile_entry["status"] == "error"


def test_mean_tile_latitude() -> None:
    assert build._mean_tile_latitude([]) == 0.0
    mean = build._mean_tile_latitude(["+00+000", "+10+000"])
    assert mean > 0.0


def test_resolution_from_options() -> None:
    assert build._resolution_from_options({}, ["+47+008"], "EPSG:4326") is None
    with pytest.raises(ValueError, match="Target resolution must be positive"):
        build._resolution_from_options({"target_resolution": -1}, ["+47+008"], "EPSG:4326")

    res = build._resolution_from_options({"target_resolution": 30}, ["+47+008"], "EPSG:4326")
    assert res is not None
    assert res[0] != 0 and res[1] != 0

    assert build._resolution_from_options({"target_resolution": 30}, ["+47+008"], "EPSG:3857") == (
        30.0,
        30.0,
    )


def test_resolution_from_options_handles_polar(monkeypatch) -> None:
    monkeypatch.setattr(build, "_mean_tile_latitude", lambda *_: 180.0)
    res = build._resolution_from_options(
        {"target_resolution": 30},
        ["+47+008"],
        "EPSG:4326",
    )
    assert res == (30.0 / 111_320.0, 30.0 / 111_320.0)


def test_apply_coverage_metrics() -> None:
    report = {"tiles": [{"tile": "+47+008"}, {"tile": "+49+008"}, {"status": "ok"}]}
    metrics = CoverageMetrics(
        total_pixels=10,
        nodata_pixels_before=2,
        nodata_pixels_after=1,
        coverage_before=0.8,
        coverage_after=0.9,
        filled_pixels=1,
        strategy="none",
    )
    build._apply_coverage_metrics(report, {"+47+008": metrics})

    assert report["tiles"][0]["metrics"]["coverage"]["coverage_after"] == 0.9


def test_triangle_guardrails(monkeypatch, tmp_path: Path) -> None:
    class DummyEstimate:
        def __init__(self, count: int) -> None:
            self.count = count
            self.width = 1
            self.height = 1

    def fake_limits(preset: str) -> dict[str, int]:
        if preset != "medium":
            raise ValueError("bad preset")
        return {"warn": 5, "max": 10}

    def fake_estimate(path: Path) -> DummyEstimate:
        return DummyEstimate(20 if "high" in str(path) else 7)

    monkeypatch.setattr(build, "triangle_limits_for_preset", fake_limits)
    monkeypatch.setattr(build, "estimate_triangles_from_raster", fake_estimate)

    report = {
        "tiles": [
            {"tile": "+47+008", "status": "ok"},
            {"tile": "+48+008", "status": "ok"},
            {"tile": "+49+008", "status": "ok"},
            {"status": "ok"},
        ]
    }
    options = {
        "density": "bad",
        "tile_dem_paths": {
            "+47+008": str(tmp_path / "high.tif"),
            "+48+008": str(tmp_path / "warn.tif"),
        },
    }

    build._apply_triangle_guardrails(report, options)
    assert report["errors"]
    assert report["warnings"]


def test_apply_xp12_checks_missing_dsf(tmp_path: Path) -> None:
    report = {"tiles": [{"tile": "+47+008", "status": "ok"}, {"status": "ok"}]}
    build._apply_xp12_checks(report, {"quality": "compat"}, tmp_path)

    assert report["tiles"][0]["status"] == "warning"


def test_apply_xp12_checks_requires_dsftool(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_checks(report, {"quality": "xp12-enhanced"}, output_dir)

    assert report["errors"]


def test_apply_xp12_checks_inventory_error(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    def raise_inventory(*_args):
        raise RuntimeError("bad")

    monkeypatch.setattr(build, "inventory_dsf_rasters", raise_inventory)

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}, {"status": "ok"}]}
    build._apply_xp12_checks(report, {"quality": "compat", "dsftool": ["tool"]}, output_dir)

    assert report["errors"]


def test_apply_xp12_checks_missing_rasters(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    summary = RasterSummary(raster_names=("foo",), soundscape_present=False, season_raster_count=0)
    monkeypatch.setattr(build, "inventory_dsf_rasters", lambda *_: summary)
    monkeypatch.setattr(build, "find_global_dsf", lambda *_: output_dir / "global.dsf")

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_checks(
        report,
        {"quality": "compat", "dsftool": ["tool"], "global_scenery": str(output_dir)},
        output_dir,
    )

    assert report["warnings"]


def test_apply_xp12_enrichment_requires_config(tmp_path: Path) -> None:
    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_enrichment(report, {"enrich_xp12": True}, tmp_path)

    assert report["errors"]


def test_apply_xp12_enrichment_skips_missing_tile(tmp_path: Path) -> None:
    report = {"tiles": [{}]}
    build._apply_xp12_enrichment(
        report,
        {"enrich_xp12": True, "dsftool": ["tool"], "global_scenery": str(tmp_path)},
        tmp_path,
    )

    assert "errors" not in report


def test_apply_xp12_enrichment_missing_dsf(tmp_path: Path) -> None:
    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_enrichment(
        report,
        {"enrich_xp12": True, "dsftool": ["tool"], "global_scenery": str(tmp_path)},
        tmp_path,
    )

    assert report["tiles"][0]["status"] == "warning"


def test_apply_xp12_enrichment_missing_global(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    monkeypatch.setattr(build, "find_global_dsf", lambda *_: None)

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_enrichment(
        report,
        {"enrich_xp12": True, "dsftool": ["tool"], "global_scenery": str(output_dir)},
        output_dir,
    )

    assert report["warnings"]


def test_apply_xp12_enrichment_failed(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    monkeypatch.setattr(build, "find_global_dsf", lambda *_: output_dir / "global.dsf")
    result = EnrichmentResult(
        status="failed",
        missing=(),
        added=(),
        backup_path=None,
        enriched_text_path=None,
        error="bad",
    )
    monkeypatch.setattr(build, "enrich_dsf_rasters", lambda *_: result)

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_enrichment(
        report,
        {"enrich_xp12": True, "dsftool": ["tool"], "global_scenery": str(output_dir)},
        output_dir,
    )

    assert report["errors"]


def test_apply_xp12_enrichment_noop(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    monkeypatch.setattr(build, "find_global_dsf", lambda *_: output_dir / "global.dsf")
    result = EnrichmentResult(
        status="no-op",
        missing=(),
        added=(),
        backup_path=None,
        enriched_text_path=None,
        error=None,
    )
    monkeypatch.setattr(build, "enrich_dsf_rasters", lambda *_: result)

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_enrichment(
        report,
        {"enrich_xp12": True, "dsftool": ["tool"], "global_scenery": str(output_dir)},
        output_dir,
    )

    assert report["tiles"][0]["messages"]


def test_apply_xp12_enrichment_enriched(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    monkeypatch.setattr(build, "find_global_dsf", lambda *_: output_dir / "global.dsf")
    result = EnrichmentResult(
        status="enriched",
        missing=("foo",),
        added=("foo",),
        backup_path="backup.dsf",
        enriched_text_path="text.txt",
        error=None,
    )
    monkeypatch.setattr(build, "enrich_dsf_rasters", lambda *_: result)
    summary = RasterSummary(raster_names=("foo",), soundscape_present=True, season_raster_count=8)
    monkeypatch.setattr(build, "inventory_dsf_rasters", lambda *_: summary)

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_enrichment(
        report,
        {"enrich_xp12": True, "dsftool": ["tool"], "global_scenery": str(output_dir)},
        output_dir,
    )

    assert report["tiles"][0]["metrics"]["xp12_enrichment"]["status"] == "enriched"


def test_apply_xp12_enrichment_postcheck_warning(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    monkeypatch.setattr(build, "find_global_dsf", lambda *_: output_dir / "global.dsf")
    result = EnrichmentResult(
        status="enriched",
        missing=("foo",),
        added=("foo",),
        backup_path="backup.dsf",
        enriched_text_path="text.txt",
        error=None,
    )
    monkeypatch.setattr(build, "enrich_dsf_rasters", lambda *_: result)
    monkeypatch.setattr(
        build,
        "inventory_dsf_rasters",
        lambda *_: (_ for _ in ()).throw(RuntimeError("bad")),
    )

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_xp12_enrichment(
        report,
        {"enrich_xp12": True, "dsftool": ["tool"], "global_scenery": str(output_dir)},
        output_dir,
    )

    assert report["warnings"]


def test_apply_autoortho_checks(monkeypatch) -> None:
    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    textures = AutoOrthoReport(
        referenced=("foo.dds",),
        missing=("missing.dds",),
        invalid=("bad.dds",),
    )
    monkeypatch.setattr(build, "scan_terrain_textures", lambda *_: textures)

    build._apply_autoortho_checks(report, {"autoortho": True}, Path("out"))
    assert report["warnings"]


def test_apply_dsf_validation_missing_dsftool() -> None:
    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_dsf_validation(report, {}, Path("out"))

    assert report["warnings"]


def test_apply_dsf_validation_missing_dsf(tmp_path: Path) -> None:
    report = {"tiles": [{"tile": "+47+008", "status": "ok"}, {"status": "ok"}]}
    build._apply_dsf_validation(report, {"dsftool": ["tool"]}, tmp_path)

    assert report["tiles"][0]["status"] == "warning"


def test_apply_dsf_validation_preserves_dsftool_command(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    captured = {}

    def fake_roundtrip(tool_cmd, *_args, **_kwargs):
        captured["cmd"] = tool_cmd

    monkeypatch.setattr(build, "roundtrip_dsf", fake_roundtrip)
    monkeypatch.setattr(
        build,
        "parse_properties_from_file",
        lambda *_: {
            "sim/west": "8",
            "sim/south": "47",
            "sim/east": "9",
            "sim/north": "48",
        },
    )
    monkeypatch.setattr(build, "parse_bounds", lambda *_: build.expected_bounds_for_tile("+47+008"))
    monkeypatch.setattr(build, "compare_bounds", lambda *_: [])

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_dsf_validation(report, {"dsftool": ["wine", "DSFTool.exe"]}, output_dir)

    assert captured["cmd"] == ["wine", "DSFTool.exe"]


def test_apply_dsf_validation_roundtrip_error(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    def raise_roundtrip(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(build, "roundtrip_dsf", raise_roundtrip)

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_dsf_validation(report, {"dsftool": ["tool"]}, output_dir)

    assert report["errors"]


def test_apply_dsf_validation_parse_error(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    monkeypatch.setattr(build, "roundtrip_dsf", lambda *_: None)

    def raise_properties(*_args):
        raise ValueError("bad")

    monkeypatch.setattr(build, "parse_properties_from_file", raise_properties)

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_dsf_validation(report, {"dsftool": ["tool"]}, output_dir)

    assert report["errors"]


def test_apply_dsf_validation_mismatch(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dsf_path = xplane_dsf_path(output_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    monkeypatch.setattr(build, "roundtrip_dsf", lambda *_: None)
    monkeypatch.setattr(build, "parse_properties_from_file", lambda *_: {"sim/west": "0"})
    monkeypatch.setattr(build, "parse_bounds", lambda *_: build.expected_bounds_for_tile("+47+008"))
    monkeypatch.setattr(build, "compare_bounds", lambda *_: ["west"])

    report = {"tiles": [{"tile": "+47+008", "status": "ok"}]}
    build._apply_dsf_validation(report, {"dsftool": ["tool"]}, output_dir)

    assert report["errors"]


def test_run_build_with_stack(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    layer_path = tmp_path / "layer.tif"
    layer_path.write_text("dem", encoding="utf-8")
    stack = DemStack(layers=(DemLayer(path=layer_path, priority=0, aoi=None, nodata=None),))

    tile_path = tmp_path / "tile.tif"
    tile_path.write_text("tile", encoding="utf-8")
    tile_result = TileResult(
        tile="+47+008",
        path=tile_path,
        bounds=(8.0, 47.0, 9.0, 48.0),
        resolution=(1.0, 1.0),
        nodata=-9999,
    )
    normalization = NormalizationResult(
        sources=(layer_path,),
        target_crs="EPSG:4326",
        mosaic_path=layer_path,
        tile_results=(tile_result,),
        coverage={},
    )

    monkeypatch.setattr(build, "get_backend", lambda *_: DummyBackend())
    monkeypatch.setattr(build, "load_dem_stack", lambda *_: stack)
    monkeypatch.setattr(build, "normalize_stack_for_tiles", lambda *_args, **_kwargs: normalization)
    monkeypatch.setattr(build, "validate_build_plan", lambda *_: None)
    monkeypatch.setattr(build, "validate_build_report", lambda *_: None)

    result = build.run_build(
        dem_paths=[],
        tiles=["+47+008"],
        backend_name="dummy",
        output_dir=output_dir,
        options={
            "quality": "compat",
            "density": "medium",
            "dem_stack_path": str(tmp_path / "stack.json"),
        },
    )

    assert result.build_report["tiles"] == []


def test_run_build_uses_normalization_cache(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    dem_path = tmp_path / "dem.tif"
    dem_path.write_text("dem", encoding="utf-8")
    tile = "+47+008"

    normalized_root = output_dir / "normalized"
    tile_path = normalized_root / "tiles" / tile / f"{tile}.tif"
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tile_path.write_text("tile", encoding="utf-8")
    mosaic_path = normalized_root / "mosaic.tif"
    mosaic_path.write_text("mosaic", encoding="utf-8")

    cache_options = build._normalization_cache_options(
        target_crs="EPSG:4326",
        resampling="bilinear",
        dst_nodata=None,
        resolution=None,
        fill_strategy="none",
        fill_value=0.0,
        backend_profile=None,
        dem_stack=None,
    )
    cache = build.NormalizationCache(
        version=build.CACHE_VERSION,
        sources=build.fingerprint_paths([dem_path]),
        fallback_sources=(),
        options=cache_options,
        tiles=(tile,),
        tile_paths={tile: str(tile_path)},
        mosaic_path=str(mosaic_path),
        coverage={
            tile: CoverageMetrics(
                total_pixels=1,
                nodata_pixels_before=0,
                nodata_pixels_after=0,
                coverage_before=1.0,
                coverage_after=1.0,
                filled_pixels=0,
                strategy="none",
            )
        },
    )
    build.write_normalization_cache(normalized_root, cache)

    def boom(*_args, **_kwargs):
        raise AssertionError("normalize_for_tiles should not run on cache hit")

    monkeypatch.setattr(build, "get_backend", lambda *_: DummyBackend())
    monkeypatch.setattr(build, "normalize_for_tiles", boom)
    monkeypatch.setattr(build, "validate_build_plan", lambda *_: None)
    monkeypatch.setattr(build, "validate_build_report", lambda *_: None)

    result = build.run_build(
        dem_paths=[dem_path],
        tiles=[tile],
        backend_name="dummy",
        output_dir=output_dir,
        options={
            "quality": "compat",
            "density": "medium",
            "normalize": True,
        },
    )

    assert result.build_report["tiles"] == []
