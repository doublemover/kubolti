from __future__ import annotations

from pathlib import Path

import pytest

from dem2dsf.overlay import (
    OverlayGenerator,
    OverlayRegistry,
    OverlayRequest,
    OverlayResult,
    _update_terrain_text,
    apply_drape_texture,
    copy_overlay_assets,
    inventory_overlay_assets,
    load_overlay_plugin,
    run_overlay,
)
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path


class DummyGenerator:
    def __init__(self, name: str) -> None:
        self.name = name

    def generate(self, request: OverlayRequest) -> OverlayResult:
        return OverlayResult(
            generator=self.name,
            artifacts={"ok": True},
            warnings=(),
            errors=(),
        )


def test_overlay_registry_duplicate() -> None:
    registry = OverlayRegistry()
    generator = DummyGenerator("dummy")
    registry.register(generator)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(generator)


def test_overlay_registry_names_sorted() -> None:
    registry = OverlayRegistry()
    registry.register(DummyGenerator("bravo"))
    registry.register(DummyGenerator("alpha"))

    assert registry.names() == ("alpha", "bravo")


def test_overlay_generator_protocol() -> None:
    request = OverlayRequest(
        build_dir=None,
        output_dir=Path("out"),
        tiles=(),
        options={},
    )
    with pytest.raises(NotImplementedError):
        OverlayGenerator.generate(None, request)  # type: ignore[reportAbstractUsage,reportArgumentType]


def test_apply_drape_texture(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    terrain_dir = build_dir / "terrain"
    terrain_dir.mkdir(parents=True)
    terrain = terrain_dir / "test.ter"
    terrain.write_text("TEXTURE ../textures/old.dds\n", encoding="utf-8")
    texture = tmp_path / "new.dds"
    texture.write_text("dds", encoding="utf-8")

    output_dir = tmp_path / "out"
    result = apply_drape_texture(build_dir, output_dir, texture)

    updated = (output_dir / "terrain" / "test.ter").read_text(encoding="utf-8")
    assert "../textures/new.dds" in updated
    assert (output_dir / "textures" / "new.dds").exists()
    assert result["terrain_updated"] == 1


def test_apply_drape_texture_missing_build_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Build directory not found"):
        apply_drape_texture(tmp_path / "missing", tmp_path / "out", tmp_path / "x.dds")


def test_apply_drape_texture_missing_terrain(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="Terrain directory not found"):
        apply_drape_texture(build_dir, tmp_path / "out", tmp_path / "x.dds")


def test_update_terrain_text_handles_png() -> None:
    updated, count = _update_terrain_text("TEXTURE_LIT old.png", "../textures/new.dds")
    assert "TEXTURE_LIT ../textures/new.dds" in updated
    assert count == 1


def test_load_overlay_plugin(tmp_path: Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_path.write_text(
        "\n".join(
            [
                "from dem2dsf.overlay import OverlayResult",
                "",
                "class Dummy:",
                "    name = 'dummy'",
                "    def generate(self, request):",
                "        return OverlayResult(",
                "            generator=self.name,",
                "            artifacts={'ok': True},",
                "            warnings=(),",
                "            errors=(),",
                "        )",
                "",
                "PLUGIN = Dummy()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    registry = OverlayRegistry()
    load_overlay_plugin(plugin_path, registry)

    assert registry.get("dummy") is not None


def test_load_overlay_plugin_register_hook(tmp_path: Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_path.write_text(
        "\n".join(
            [
                "from dem2dsf.overlay import OverlayResult",
                "def register(registry):",
                "    class Dummy:",
                "        name = 'hook'",
                "        def generate(self, request):",
                "            return OverlayResult(",
                "                generator=self.name,",
                "                artifacts={'ok': True},",
                "                warnings=(),",
                "                errors=(),",
                "            )",
                "    registry.register(Dummy())",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    registry = OverlayRegistry()
    load_overlay_plugin(plugin_path, registry)

    assert registry.get("hook") is not None


def test_load_overlay_plugin_missing_spec(tmp_path: Path, monkeypatch) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("importlib.util.spec_from_file_location", lambda *_: None)

    with pytest.raises(ValueError, match="Unable to load plugin"):
        load_overlay_plugin(plugin_path, OverlayRegistry())


def test_run_overlay_with_plugin(tmp_path: Path) -> None:
    plugin_path = tmp_path / "plugin.py"
    plugin_path.write_text(
        "\n".join(
            [
                "from dem2dsf.overlay import OverlayResult",
                "",
                "class Dummy:",
                "    name = 'dummy'",
                "    def generate(self, request):",
                "        return OverlayResult(",
                "            generator=self.name,",
                "            artifacts={'ok': True},",
                "            warnings=(),",
                "            errors=(),",
                "        )",
                "",
                "PLUGIN = Dummy()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_overlay(
        build_dir=None,
        output_dir=tmp_path / "out",
        generator="dummy",
        tiles=(),
        options={},
        plugin_paths=[plugin_path],
    )

    assert report["artifacts"]["ok"] is True


def test_run_overlay_drape_requires_texture(tmp_path: Path) -> None:
    report = run_overlay(
        build_dir=tmp_path,
        output_dir=tmp_path / "out",
        generator="drape",
        tiles=(),
        options={},
    )

    assert "drape requires a texture path" in report["errors"]


def test_run_overlay_drape_requires_build_dir(tmp_path: Path) -> None:
    report = run_overlay(
        build_dir=None,
        output_dir=tmp_path / "out",
        generator="drape",
        tiles=(),
        options={"texture": "demo.dds"},
    )

    assert "drape requires --build-dir" in report["errors"]


def test_run_overlay_drape_success(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    terrain_dir = build_dir / "terrain"
    terrain_dir.mkdir(parents=True)
    (terrain_dir / "tile.ter").write_text("TEXTURE ../textures/old.dds\n", encoding="utf-8")
    texture = tmp_path / "new.dds"
    texture.write_text("dds", encoding="utf-8")

    report = run_overlay(
        build_dir=build_dir,
        output_dir=tmp_path / "out",
        generator="drape",
        tiles=(),
        options={"texture": str(texture)},
    )

    assert report["artifacts"]["terrain_updated"] == 1


def test_copy_overlay_assets_subset(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")
    terrain_dir = build_dir / "terrain"
    terrain_dir.mkdir(parents=True)
    (terrain_dir / "demo.ter").write_text("TEXTURE foo.dds\n", encoding="utf-8")
    textures_dir = build_dir / "textures"
    textures_dir.mkdir(parents=True)
    (textures_dir / "foo.dds").write_text("dds", encoding="utf-8")

    output_dir = tmp_path / "overlay"
    artifacts = copy_overlay_assets(
        build_dir=build_dir,
        output_dir=output_dir,
        tiles=("+47+008",),
        include_terrain=True,
        include_textures=False,
    )

    assert xplane_dsf_path(output_dir, "+47+008").exists()
    assert (output_dir / "terrain" / "demo.ter").exists()
    assert not (output_dir / "textures").exists()
    assert artifacts["tiles_copied"] == ["+47+008"]
    assert artifacts["texture_files"] == 0


def test_run_overlay_copy_missing_tiles(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    report = run_overlay(
        build_dir=build_dir,
        output_dir=tmp_path / "out",
        generator="copy",
        tiles=("+47+009",),
        options={"include_terrain": False, "include_textures": False},
    )

    assert "Missing tiles" in report["warnings"][0]


def test_inventory_overlay_assets(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")
    terrain_dir = build_dir / "terrain"
    terrain_dir.mkdir(parents=True)
    (terrain_dir / "demo.ter").write_text("\nTEXTURE foo.dds\n", encoding="utf-8")

    output_dir = tmp_path / "out"
    artifacts = inventory_overlay_assets(
        build_dir=build_dir,
        output_dir=output_dir,
        tiles=(),
    )

    assert (output_dir / "overlay_inventory.json").exists()
    assert artifacts["tile_count"] == 1


def test_copy_overlay_assets_requires_build_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Build directory not found"):
        copy_overlay_assets(
            build_dir=tmp_path / "missing",
            output_dir=tmp_path / "out",
            tiles=(),
            include_terrain=True,
            include_textures=True,
        )


def test_copy_overlay_assets_requires_earth_dir(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="Earth nav data not found"):
        copy_overlay_assets(
            build_dir=build_dir,
            output_dir=tmp_path / "out",
            tiles=(),
            include_terrain=True,
            include_textures=True,
        )


def test_copy_overlay_assets_full_copy(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")
    terrain_dir = build_dir / "terrain"
    terrain_dir.mkdir(parents=True)
    (terrain_dir / "demo.ter").write_text("TEXTURE foo.dds\n", encoding="utf-8")
    textures_dir = build_dir / "textures"
    textures_dir.mkdir(parents=True)
    (textures_dir / "foo.dds").write_text("dds", encoding="utf-8")

    output_dir = tmp_path / "out"
    artifacts = copy_overlay_assets(
        build_dir=build_dir,
        output_dir=output_dir,
        tiles=(),
        include_terrain=True,
        include_textures=True,
    )

    assert artifacts["dsf_files"] == 1
    assert artifacts["texture_files"] == 1


def test_run_overlay_copy_requires_build_dir(tmp_path: Path) -> None:
    report = run_overlay(
        build_dir=None,
        output_dir=tmp_path / "out",
        generator="copy",
        tiles=(),
        options={},
    )

    assert "copy requires --build-dir" in report["errors"]


def test_run_overlay_copy_missing_earth_dir(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    report = run_overlay(
        build_dir=build_dir,
        output_dir=tmp_path / "out",
        generator="copy",
        tiles=(),
        options={},
    )

    assert "Earth nav data not found" in report["errors"][0]


def test_run_overlay_copy_warns_missing_assets(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    report = run_overlay(
        build_dir=build_dir,
        output_dir=tmp_path / "out",
        generator="copy",
        tiles=(),
        options={},
    )

    assert "No terrain files copied." in report["warnings"]
    assert "No texture files copied." in report["warnings"]


def test_inventory_overlay_assets_requires_build_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Build directory not found"):
        inventory_overlay_assets(
            build_dir=tmp_path / "missing",
            output_dir=tmp_path / "out",
            tiles=(),
        )


def test_inventory_overlay_assets_requires_earth_dir(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="Earth nav data not found"):
        inventory_overlay_assets(
            build_dir=build_dir,
            output_dir=tmp_path / "out",
            tiles=(),
        )


def test_inventory_overlay_assets_tile_filter(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")
    output_dir = tmp_path / "out"

    artifacts = inventory_overlay_assets(
        build_dir=build_dir,
        output_dir=output_dir,
        tiles=("+47+008",),
    )

    assert artifacts["tile_count"] == 1


def test_run_overlay_inventory_requires_build_dir(tmp_path: Path) -> None:
    report = run_overlay(
        build_dir=None,
        output_dir=tmp_path / "out",
        generator="inventory",
        tiles=(),
        options={},
    )

    assert "inventory requires --build-dir" in report["errors"]


def test_run_overlay_inventory_missing_earth_dir(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    report = run_overlay(
        build_dir=build_dir,
        output_dir=tmp_path / "out",
        generator="inventory",
        tiles=(),
        options={},
    )

    assert "Earth nav data not found" in report["errors"][0]


def test_run_overlay_inventory_success(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    dsf_path = xplane_dsf_path(build_dir, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    report = run_overlay(
        build_dir=build_dir,
        output_dir=tmp_path / "out",
        generator="inventory",
        tiles=(),
        options={},
    )

    assert report["artifacts"]["tile_count"] == 1


def test_run_overlay_unknown_generator(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown overlay generator"):
        run_overlay(
            build_dir=None,
            output_dir=tmp_path / "out",
            generator="missing",
            tiles=(),
            options={},
        )
