from __future__ import annotations

from pathlib import Path

import pytest

from dem2dsf import xp12
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path


class DummyResult:
    def __init__(self, returncode: int, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr


def test_parse_raster_names_variants() -> None:
    text = "\n".join(
        [
            'RASTER_DEF 0 "soundscape"',
            "RASTER_DEF 1 season_spring_start",
            "raster_def 2 raster_foo",
            "raster_def 3 1234",
            "raster_def 4 name_with_letters",
            "# raster_def 5 hidden",
        ]
    )
    names = xp12.parse_raster_names(text)
    assert "soundscape" in names
    assert "season_spring_start" in names
    assert "name_with_letters" in names
    assert "raster_foo" not in names


def test_extract_raster_blocks() -> None:
    text = "\n".join(
        [
            'raster_def 0 "soundscape"',
            "raster_def 1 season_summer",
        ]
    )
    blocks = xp12._extract_raster_blocks(text)
    assert "soundscape" in blocks
    assert "season_summer" in blocks
    assert blocks["soundscape"].index == 0


def test_extract_raster_blocks_skips_empty() -> None:
    text = "raster_def 0 1234\n"
    blocks = xp12._extract_raster_blocks(text)
    assert blocks == {}


def test_is_xp12_raster() -> None:
    assert xp12._is_xp12_raster("soundscape") is True
    assert xp12._is_xp12_raster("season_spring_start") is True
    assert xp12._is_xp12_raster("heightmap") is False


def test_summarize_rasters_counts() -> None:
    summary = xp12.summarize_rasters(["soundscape", "season_summer", "season_winter"])
    assert summary.soundscape_present is True
    assert summary.season_raster_count == 2


def test_inventory_dsf_rasters_errors(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*_args, **_kwargs):
        return DummyResult(1, "fail")

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    with pytest.raises(RuntimeError, match="dsf2text failed"):
        xp12.inventory_dsf_rasters(Path("tool"), tmp_path / "tile.dsf", tmp_path)


def test_inventory_dsf_rasters_success(monkeypatch, tmp_path: Path) -> None:
    def fake_run(_tool, args, **_kwargs):
        if "--dsf2text" in args:
            Path(args[-1]).write_text(
                'RASTER_DEF 0 "soundscape"\nRASTER_DEF 1 season_summer\n',
                encoding="utf-8",
            )
            return DummyResult(0)
        return DummyResult(1, "bad")

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    summary = xp12.inventory_dsf_rasters(Path("tool"), tmp_path / "tile.dsf", tmp_path)
    assert summary.soundscape_present is True
    assert summary.season_raster_count == 1


def test_enrich_dsf_rasters_dsf2text_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run(_tool, args, **_kwargs):
        return DummyResult(1, "bad")

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    result = xp12.enrich_dsf_rasters(
        Path("tool"),
        tmp_path / "tile.dsf",
        tmp_path / "global.dsf",
        tmp_path / "work",
    )
    assert result.status == "failed"


def test_enrich_dsf_rasters_global_dsf2text_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run(_tool, args, **_kwargs):
        if any("global.dsf" in str(arg) for arg in args):
            return DummyResult(1, "bad")
        if "--dsf2text" in args:
            Path(args[-1]).write_text("property foo bar\n", encoding="utf-8")
        return DummyResult(0)

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    result = xp12.enrich_dsf_rasters(
        Path("tool"),
        tmp_path / "tile.dsf",
        tmp_path / "global.dsf",
        tmp_path / "work",
    )
    assert result.status == "failed"


def test_enrich_dsf_rasters_noop(monkeypatch, tmp_path: Path) -> None:
    def fake_run(_tool, args, **_kwargs):
        if "--dsf2text" in args:
            Path(args[-1]).write_text("RASTER_DEF 0 soundscape\n", encoding="utf-8")
            return DummyResult(0)
        return DummyResult(0)

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    result = xp12.enrich_dsf_rasters(
        Path("tool"),
        tmp_path / "tile.dsf",
        tmp_path / "global.dsf",
        tmp_path / "work",
    )
    assert result.status == "no-op"


def test_enrich_dsf_rasters_text2dsf_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run(_tool, args, **_kwargs):
        if "--dsf2text" in args:
            if any("global.dsf" in str(arg) for arg in args):
                Path(args[-1]).write_text("raster_def 0 soundscape\n", encoding="utf-8")
            else:
                Path(args[-1]).write_text("property foo bar\n", encoding="utf-8")
            return DummyResult(0)
        if "--text2dsf" in args:
            return DummyResult(1, "no")
        return DummyResult(0)

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    result = xp12.enrich_dsf_rasters(
        Path("tool"),
        tmp_path / "tile.dsf",
        tmp_path / "global.dsf",
        tmp_path / "work",
    )
    assert result.status == "failed"


def test_enrich_dsf_rasters_success(monkeypatch, tmp_path: Path) -> None:
    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_text("dsf", encoding="utf-8")

    def fake_run(_tool, args, **_kwargs):
        if "--dsf2text" in args:
            if any("global.dsf" in str(arg) for arg in args):
                Path(args[-1]).write_text(
                    "raster_def 0 soundscape\nproperty foo bar\n",
                    encoding="utf-8",
                )
            else:
                Path(args[-1]).write_text("property foo bar\n", encoding="utf-8")
            return DummyResult(0)
        if "--text2dsf" in args:
            Path(args[-1]).write_text("dsf", encoding="utf-8")
            return DummyResult(0)
        return DummyResult(1, "bad")

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    result = xp12.enrich_dsf_rasters(
        Path("tool"),
        dsf_path,
        tmp_path / "global.dsf",
        tmp_path / "work",
    )
    assert result.status == "enriched"
    assert result.backup_path is not None
    assert Path(result.backup_path).exists()


def test_enrich_dsf_rasters_copies_sidecars(monkeypatch, tmp_path: Path) -> None:
    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_text("dsf", encoding="utf-8")

    def fake_run(_tool, args, **_kwargs):
        if "--dsf2text" in args:
            text_path = Path(args[-1])
            if any("global.dsf" in str(arg) for arg in args):
                text_path.write_text(
                    "raster_def 0 soundscape\nproperty foo bar\n",
                    encoding="utf-8",
                )
                sidecar = text_path.with_name(f"{text_path.name}.0.soundscape.raw")
                sidecar.write_text("raw", encoding="utf-8")
            else:
                text_path.write_text("property foo bar\n", encoding="utf-8")
            return DummyResult(0)
        if "--text2dsf" in args:
            Path(args[-1]).write_text("dsf", encoding="utf-8")
            return DummyResult(0)
        return DummyResult(1, "bad")

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    result = xp12.enrich_dsf_rasters(
        Path("tool"),
        dsf_path,
        tmp_path / "global.dsf",
        tmp_path / "work",
    )
    assert result.status == "enriched"
    enriched_sidecar = tmp_path / "work" / "tile.enriched.txt.0.soundscape.raw"
    assert enriched_sidecar.exists()


def test_enrich_dsf_rasters_inserts_before_bounds(monkeypatch, tmp_path: Path) -> None:
    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_text("dsf", encoding="utf-8")

    def fake_run(_tool, args, **_kwargs):
        if "--dsf2text" in args:
            if any("global.dsf" in str(arg) for arg in args):
                Path(args[-1]).write_text(
                    "raster_def 0 soundscape\n"
                    "raster_data 0 version=1 bpp=2 flags=0 width=1 height=1 "
                    "scale=1 offset=0 soundscape.raw\n",
                    encoding="utf-8",
                )
            else:
                Path(args[-1]).write_text(
                    "\n".join(
                        [
                            "PROPERTY sim/overlay 1",
                            "PROPERTY sim/west 8",
                            "PROPERTY sim/south 47",
                            "PROPERTY sim/east 9",
                            "PROPERTY sim/north 48",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
            return DummyResult(0)
        if "--text2dsf" in args:
            Path(args[-1]).write_text("dsf", encoding="utf-8")
            return DummyResult(0)
        return DummyResult(1, "bad")

    monkeypatch.setattr(xp12, "run_dsftool", fake_run)

    result = xp12.enrich_dsf_rasters(
        Path("tool"),
        dsf_path,
        tmp_path / "global.dsf",
        tmp_path / "work",
    )
    assert result.status == "enriched"
    enriched_text = (tmp_path / "work" / "tile.enriched.txt").read_text(encoding="utf-8")
    lines = [line.strip() for line in enriched_text.splitlines() if line.strip()]
    assert lines.index("raster_def 0 soundscape") < lines.index("PROPERTY sim/west 8")


def test_find_global_dsf(tmp_path: Path) -> None:
    root = tmp_path / "global"
    dsf_path = xplane_dsf_path(root, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    assert xp12.find_global_dsf(root, "+47+008") == dsf_path

    fallback_root = tmp_path / "fallback"
    fallback_root.mkdir()
    other = fallback_root / "+47+008.dsf"
    other.write_text("dsf", encoding="utf-8")

    assert xp12.find_global_dsf(fallback_root, "+47+008") is None

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    assert xp12.find_global_dsf(empty_root, "+47+008") is None
