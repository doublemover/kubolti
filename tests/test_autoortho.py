from __future__ import annotations

from pathlib import Path

from dem2dsf.autoortho import _extract_texture_refs, scan_terrain_textures


def test_scan_terrain_textures(tmp_path: Path) -> None:
    terrain_dir = tmp_path / "terrain"
    textures_dir = tmp_path / "textures"
    terrain_dir.mkdir()
    textures_dir.mkdir()

    valid_tex = textures_dir / "123_456_BI_17.dds"
    valid_tex.write_text("dds", encoding="utf-8")

    ter_file = terrain_dir / "tile.ter"
    ter_file.write_text(
        "BASE_TEX ../textures/123_456_BI_17.dds\n"
        "BASE_TEX ../textures/missing.dds\n"
        "BASE_TEX ../textures/bad_name.dds\n",
        encoding="utf-8",
    )

    report = scan_terrain_textures(tmp_path)
    assert "../textures/missing.dds" in report.missing
    assert "../textures/bad_name.dds" in report.invalid
    assert "../textures/123_456_BI_17.dds" in report.referenced


def test_extract_texture_refs_filters_tokens() -> None:
    text = "\n".join(
        [
            "TEXTURE foo.dds.tmp",
            "TEXTURE bar.DDS",
            "TEXTURE_LIT baz.png",
        ]
    )
    refs = _extract_texture_refs(text)
    assert "bar.DDS" in refs
    assert "foo.dds.tmp" not in refs
    assert "baz.png" not in refs


def test_scan_terrain_textures_absolute_refs(tmp_path: Path) -> None:
    terrain_dir = tmp_path / "terrain"
    terrain_dir.mkdir()
    texture = tmp_path / "abs.dds"
    texture.write_text("dds", encoding="utf-8")
    (terrain_dir / "tile.ter").write_text(
        f"TEXTURE {texture}\n",
        encoding="utf-8",
    )

    report = scan_terrain_textures(tmp_path)
    assert str(texture) in report.referenced
    assert str(texture) not in report.missing


def test_scan_terrain_textures_ignores_unreadable(monkeypatch, tmp_path: Path) -> None:
    terrain_dir = tmp_path / "terrain"
    terrain_dir.mkdir()
    (terrain_dir / "tile.ter").write_text("TEXTURE ../textures/skip.dds\n", encoding="utf-8")

    def boom(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", boom)

    report = scan_terrain_textures(tmp_path)
    assert report.referenced == ()
