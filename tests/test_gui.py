from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dem2dsf import gui


def test_parse_list() -> None:
    assert gui.parse_list("a, b ,c") == ["a", "b", "c"]
    assert gui.parse_list("") == []


def test_parse_optional_float() -> None:
    assert gui.parse_optional_float("1.5") == pytest.approx(1.5)
    assert gui.parse_optional_float(" ") is None


def test_parse_optional_int() -> None:
    assert gui.parse_optional_int("5") == 5
    assert gui.parse_optional_int(" ") is None


def test_parse_command() -> None:
    assert gui.parse_command("python runner.py --demo") == [
        "python",
        "runner.py",
        "--demo",
    ]
    assert gui.parse_command(" ") is None


def test_invalid_tiles() -> None:
    assert gui._invalid_tiles(["+47+008"]) == []
    assert gui._invalid_tiles(["47+008", "+47+08"]) == ["47+008", "+47+08"]


def test_gui_prefs_roundtrip(tmp_path: Path, monkeypatch) -> None:
    prefs_path = tmp_path / "prefs.json"
    monkeypatch.setenv(gui.ENV_GUI_PREFS, str(prefs_path))
    payload = {
        "build": {"tiles": "+47+008", "dry_run": True},
        "publish": {"output_zip": "build.zip", "dsf_7z": True, "dsf_7z_backup": True},
    }
    gui.save_gui_prefs(payload)
    loaded = gui.load_gui_prefs()
    assert loaded["build"]["tiles"] == "+47+008"
    assert loaded["build"]["dry_run"] is True
    assert loaded["publish"]["dsf_7z"] is True
    assert loaded["publish"]["dsf_7z_backup"] is True


def test_gui_prefs_invalid_json(tmp_path: Path, monkeypatch) -> None:
    prefs_path = tmp_path / "prefs.json"
    prefs_path.write_text("{", encoding="utf-8")
    monkeypatch.setenv(gui.ENV_GUI_PREFS, str(prefs_path))
    loaded = gui.load_gui_prefs()
    assert loaded == {"build": {}, "publish": {}}


def test_gui_prefs_explicit_path(tmp_path: Path) -> None:
    prefs_path = tmp_path / "prefs.json"
    prefs_path.write_text(
        json.dumps({"build": {"tiles": "+47+008"}, "publish": {}}),
        encoding="utf-8",
    )
    loaded = gui.load_gui_prefs(prefs_path)
    assert loaded["build"]["tiles"] == "+47+008"


def test_normalize_prefs_invalid_payload() -> None:
    assert gui._normalize_prefs([]) == {"build": {}, "publish": {}}


def test_apply_prefs_sets_values() -> None:
    class DummyVar:
        def __init__(self) -> None:
            self.value = None

        def get(self):
            return self.value

        def set(self, value) -> None:
            self.value = value

    vars_map = {"a": DummyVar(), "b": DummyVar(), "c": DummyVar()}
    gui._apply_prefs(vars_map, {"a": "demo", "b": None, "c": False})
    assert vars_map["a"].get() == "demo"
    assert vars_map["b"].get() is None
    assert vars_map["c"].get() is False


def test_default_ortho_runner() -> None:
    assert gui._default_ortho_runner() is not None


def test_default_ortho_runner_meipass(monkeypatch, tmp_path: Path) -> None:
    runner_dir = tmp_path / "scripts"
    runner_dir.mkdir()
    runner_path = runner_dir / "ortho4xp_runner.py"
    runner_path.write_text("# stub", encoding="utf-8")

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert gui._default_ortho_runner() == [sys.executable, str(runner_path)]


def test_build_form_to_request() -> None:
    values = {
        "dems": "a.tif, b.tif",
        "dem_stack": "",
        "aoi_path": "area.geojson",
        "aoi_crs": "EPSG:4326",
        "tiles": "+47+008",
        "infer_tiles": True,
        "output_dir": "out",
        "quality": "xp12-enhanced",
        "density": "high",
        "autoortho": True,
        "skip_normalize": False,
        "tile_jobs": "4",
        "triangle_warn": "100",
        "triangle_max": "200",
        "allow_triangle_overage": True,
        "runner_cmd": "python runner.py --demo",
        "ortho_root": "",
        "ortho_python": "",
        "ortho_batch": False,
        "dsftool_path": "dsftool.exe",
        "target_crs": "EPSG:4326",
        "resampling": "nearest",
        "target_resolution": "30",
        "dst_nodata": "99",
        "fill_strategy": "constant",
        "fill_value": "5",
        "fallback_dems": "fallback.tif",
        "global_scenery": "Global Scenery",
        "enrich_xp12": True,
        "profile": True,
        "metrics_json": "metrics.json",
        "dry_run": True,
    }
    dem_paths, tiles, output_dir, options = gui.build_form_to_request(values)
    assert dem_paths == [Path("a.tif"), Path("b.tif")]
    assert tiles == ["+47+008"]
    assert output_dir == Path("out")
    assert options["fill_value"] == 5.0
    assert options["dst_nodata"] == 99.0
    assert options["quality"] == "xp12-enhanced"
    assert options["density"] == "high"
    assert options["autoortho"] is True
    assert options["aoi"] == "area.geojson"
    assert options["aoi_crs"] == "EPSG:4326"
    assert options["infer_tiles"] is True
    assert options["normalize"] is True
    assert options["tile_jobs"] == 4
    assert options["triangle_warn"] == 100
    assert options["triangle_max"] == 200
    assert options["allow_triangle_overage"] is True
    assert options["runner"] == ["python", "runner.py", "--demo"]
    assert options["dsftool"] == ["dsftool.exe"]
    assert options["global_scenery"] == "Global Scenery"
    assert options["enrich_xp12"] is True
    assert options["profile"] is True
    assert options["metrics_json"] == "metrics.json"


def test_build_form_to_request_with_ortho_root(monkeypatch) -> None:
    runner_path = Path("runner.py")
    monkeypatch.setattr(gui, "_default_ortho_runner", lambda: [sys.executable, str(runner_path)])

    values = {
        "dems": "a.tif",
        "dem_stack": "",
        "tiles": "+47+008",
        "output_dir": "out",
        "quality": "compat",
        "density": "medium",
        "autoortho": False,
        "skip_normalize": False,
        "tile_jobs": "1",
        "triangle_warn": "",
        "triangle_max": "",
        "allow_triangle_overage": False,
        "runner_cmd": "",
        "ortho_root": "C:/Ortho4XP",
        "ortho_python": "C:/Python.exe",
        "ortho_batch": True,
        "dsftool_path": "",
        "target_crs": "EPSG:4326",
        "resampling": "nearest",
        "target_resolution": "",
        "dst_nodata": "",
        "fill_strategy": "none",
        "fill_value": "",
        "fallback_dems": "",
        "global_scenery": "",
        "enrich_xp12": False,
        "profile": False,
        "metrics_json": "",
        "dry_run": False,
    }
    _dem_paths, _tiles, _output_dir, options = gui.build_form_to_request(values)
    assert options["runner"][0] == sys.executable
    assert "C:/Ortho4XP" in options["runner"]
    assert "--python" in options["runner"]
    assert "C:/Python.exe" in options["runner"]
    assert "--batch" in options["runner"]


def test_build_form_to_request_uses_tool_defaults(monkeypatch) -> None:
    def fake_load_tool_paths():
        return {
            "ortho4xp": Path("Ortho4XP_v140.py"),
            "dsftool": Path("DSFTool.exe"),
        }

    monkeypatch.setattr(gui, "load_tool_paths", fake_load_tool_paths)
    monkeypatch.setattr(gui, "_default_ortho_runner", lambda: [sys.executable, "runner.py"])
    monkeypatch.setattr(gui, "ortho_root_from_paths", lambda _paths: Path("C:/Ortho4XP"))

    values = {
        "dems": "a.tif",
        "dem_stack": "",
        "tiles": "+47+008",
        "output_dir": "out",
        "quality": "compat",
        "density": "medium",
        "autoortho": False,
        "skip_normalize": False,
        "tile_jobs": "1",
        "triangle_warn": "",
        "triangle_max": "",
        "allow_triangle_overage": False,
        "runner_cmd": "",
        "ortho_root": "",
        "ortho_python": "python",
        "ortho_batch": True,
        "dsftool_path": "",
        "target_crs": "EPSG:4326",
        "resampling": "nearest",
        "target_resolution": "",
        "dst_nodata": "",
        "fill_strategy": "none",
        "fill_value": "",
        "fallback_dems": "",
        "global_scenery": "",
        "enrich_xp12": False,
        "profile": False,
        "metrics_json": "",
        "dry_run": False,
    }
    _dem_paths, _tiles, _output_dir, options = gui.build_form_to_request(values)
    assert options["runner"][0] == sys.executable
    assert "--ortho-root" in options["runner"]
    assert "--python" in options["runner"]
    assert "--batch" in options["runner"]
    assert options["dsftool"] == ["DSFTool.exe"]


def test_apply_runner_overrides_adds_root() -> None:
    options = {"runner": ["python", "runner.py"]}
    gui._apply_runner_overrides(
        options,
        ortho_root="C:/Ortho4XP",
        ortho_python=None,
        ortho_batch=False,
        persist_config=False,
    )
    assert "--ortho-root" in options["runner"]


def test_publish_form_to_request() -> None:
    values = {
        "build_dir": "build",
        "output_zip": "out.zip",
        "dsf_7z": True,
        "dsf_7z_backup": True,
        "sevenzip_path": "7z",
        "allow_missing_7z": True,
    }
    build_dir, output_zip, options = gui.publish_form_to_request(values)
    assert build_dir == Path("build")
    assert output_zip == Path("out.zip")
    assert options["dsf_7z"] is True
    assert options["dsf_7z_backup"] is True


def test_launch_gui_with_stub_tkinter(monkeypatch, tmp_path: Path) -> None:
    commands = []
    errors = []
    protocols = {}

    class DummyWidget:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def grid(self, *args, **kwargs) -> None:
            return None

        def pack(self, *args, **kwargs) -> None:
            return None

        def columnconfigure(self, *args, **kwargs) -> None:
            return None

        def insert(self, *args, **kwargs) -> None:
            return None

        def see(self, *args, **kwargs) -> None:
            return None

    class DummyVar:
        def __init__(self, value=None) -> None:
            self._value = value

        def get(self):
            return self._value

        def set(self, value) -> None:
            self._value = value

    class DummyTk(DummyWidget):
        def title(self, *args, **kwargs) -> None:
            return None

        def mainloop(self) -> None:
            return None

        def destroy(self) -> None:
            return None

        def protocol(self, name, func) -> None:
            protocols[name] = func

    class DummyNotebook(DummyWidget):
        def add(self, *args, **kwargs) -> None:
            return None

    class DummyButton(DummyWidget):
        def __init__(self, *args, **kwargs) -> None:
            commands.append((kwargs.get("text"), kwargs.get("command")))

    tk_module = SimpleNamespace(
        Tk=DummyTk,
        StringVar=DummyVar,
        BooleanVar=DummyVar,
        Text=DummyWidget,
    )
    ttk_module = SimpleNamespace(
        Notebook=DummyNotebook,
        Frame=DummyWidget,
        Label=DummyWidget,
        Entry=DummyWidget,
        Combobox=DummyWidget,
        Checkbutton=DummyWidget,
        Button=DummyButton,
    )
    messagebox = SimpleNamespace(showerror=lambda *_: errors.append("error"))
    filedialog = SimpleNamespace(
        askopenfilename=lambda **_kwargs: "demo.json",
        askopenfilenames=lambda **_kwargs: ("a.tif", "b.tif"),
        askdirectory=lambda **_kwargs: str(tmp_path),
        asksaveasfilename=lambda **_kwargs: str(tmp_path / "metrics.json"),
    )
    tk_module.ttk = ttk_module
    tk_module.messagebox = messagebox
    tk_module.filedialog = filedialog

    monkeypatch.setitem(sys.modules, "tkinter", tk_module)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", ttk_module)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", filedialog)

    gui.launch_gui()
    apply_command = next(cmd for text, cmd in commands if text == "Apply")
    browse_commands = [cmd for text, cmd in commands if text == "Browse"]
    build_command = next(cmd for text, cmd in commands if text == "Run Build")
    publish_command = next(cmd for text, cmd in commands if text == "Publish")

    monkeypatch.setenv(gui.ENV_GUI_PREFS, str(tmp_path / "prefs.json"))
    apply_command()
    for command in browse_commands:
        command()

    monkeypatch.setattr(gui, "get_preset", lambda *_args, **_kwargs: None)
    apply_command()
    assert errors

    def fake_build_request(_values):
        return [], [], Path("out"), {}

    monkeypatch.setattr(gui, "build_form_to_request", fake_build_request)
    build_command()
    assert errors

    monkeypatch.setattr(
        gui,
        "build_form_to_request",
        lambda _values: ([], ["+47+008"], Path("out"), {}),
    )
    build_command()
    assert errors

    monkeypatch.setattr(
        gui,
        "build_form_to_request",
        lambda _values: ([Path("dem.tif")], ["+47+008"], Path("out"), {}),
    )

    def fail_build(**_kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(gui, "run_build", fail_build)
    build_command()
    assert errors

    monkeypatch.setattr(gui, "run_build", lambda **_kwargs: None)
    monkeypatch.setattr(
        gui,
        "save_gui_prefs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("fail")),
    )
    build_command()

    options = {
        "dsf_7z": False,
        "dsf_7z_backup": False,
        "sevenzip_path": None,
        "allow_missing_sevenzip": False,
    }
    monkeypatch.setattr(
        gui,
        "publish_form_to_request",
        lambda _values: (Path("build"), Path("out.zip"), options),
    )

    def fail_publish(*_args, **_kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(gui, "publish_build", fail_publish)
    publish_command()
    assert errors

    monkeypatch.setattr(gui, "publish_build", lambda *_args, **_kwargs: {"zip_path": "out.zip"})
    publish_command()
    protocols["WM_DELETE_WINDOW"]()


def test_gui_main_invokes_launch(monkeypatch) -> None:
    called = {"ok": False}

    def fake_launch() -> None:
        called["ok"] = True

    monkeypatch.setattr(gui, "launch_gui", fake_launch)

    assert gui.main() == 0
    assert called["ok"] is True


def test_gui_module_entrypoint(monkeypatch) -> None:
    class DummyWidget:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def grid(self, *args, **kwargs) -> None:
            return None

        def pack(self, *args, **kwargs) -> None:
            return None

        def columnconfigure(self, *args, **kwargs) -> None:
            return None

        def insert(self, *args, **kwargs) -> None:
            return None

        def see(self, *args, **kwargs) -> None:
            return None

    class DummyVar:
        def __init__(self, value=None) -> None:
            self._value = value

        def get(self):
            return self._value

        def set(self, value) -> None:
            self._value = value

    class DummyTk(DummyWidget):
        def title(self, *args, **kwargs) -> None:
            return None

        def mainloop(self) -> None:
            return None

        def destroy(self) -> None:
            return None

        def protocol(self, *_args, **_kwargs) -> None:
            return None

    class DummyNotebook(DummyWidget):
        def add(self, *args, **kwargs) -> None:
            return None

    tk_module = SimpleNamespace(
        Tk=DummyTk,
        StringVar=DummyVar,
        BooleanVar=DummyVar,
        Text=DummyWidget,
    )
    ttk_module = SimpleNamespace(
        Notebook=DummyNotebook,
        Frame=DummyWidget,
        Label=DummyWidget,
        Entry=DummyWidget,
        Combobox=DummyWidget,
        Checkbutton=DummyWidget,
        Button=DummyWidget,
    )
    messagebox = SimpleNamespace(showerror=lambda *_: None)
    filedialog = SimpleNamespace(
        askopenfilename=lambda **_kwargs: "",
        askopenfilenames=lambda **_kwargs: (),
        askdirectory=lambda **_kwargs: "",
        asksaveasfilename=lambda **_kwargs: "",
    )
    tk_module.ttk = ttk_module
    tk_module.messagebox = messagebox
    tk_module.filedialog = filedialog

    monkeypatch.setitem(sys.modules, "tkinter", tk_module)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", ttk_module)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", messagebox)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", filedialog)
    monkeypatch.setattr(sys, "argv", ["dem2dsf.gui"])
    sys.modules.pop("dem2dsf.gui", None)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("dem2dsf.gui", run_name="__main__")

    assert exc.value.code == 0
