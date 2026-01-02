from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dem2dsf.doctor import (
    check_command,
    check_ortho4xp_python,
    check_ortho4xp_version,
    check_overlay_source,
    check_python_version,
    run_doctor,
)


def test_doctor_defaults() -> None:
    results = run_doctor(ortho_runner=None, dsftool_path=None)
    names = {result.name for result in results}
    assert "python" in names
    assert "rasterio" in names
    assert "pyproj" in names
    assert "ortho4xp_version" in names
    assert "ortho4xp_python" in names
    assert "overlay_source" in names
    assert "ortho4xp_runner" in names
    assert "dsftool" in names
    assert "ddstool" in names


def test_check_ortho4xp_version_ok(tmp_path: Path) -> None:
    script = tmp_path / "Ortho4XP_v140.py"
    script.write_text("pass", encoding="utf-8")
    result = check_ortho4xp_version(None, {"ortho4xp": script})
    assert result.status == "ok"


def test_check_ortho4xp_version_warns(tmp_path: Path) -> None:
    script = tmp_path / "Ortho4XP_v130.py"
    script.write_text("pass", encoding="utf-8")
    result = check_ortho4xp_version(None, {"ortho4xp": script})
    assert result.status == "warn"


def test_check_ortho4xp_version_missing_script(tmp_path: Path) -> None:
    missing = tmp_path / "missing.py"
    runner = ["runner", "--ortho-script", str(missing)]
    result = check_ortho4xp_version(runner, {})
    assert result.status == "error"


def test_check_ortho4xp_version_root_override_missing(tmp_path: Path) -> None:
    runner = ["runner", f"--ortho-root={tmp_path / 'missing'}"]
    result = check_ortho4xp_version(runner, {})
    assert result.status == "error"


def test_check_ortho4xp_version_env_root_missing(monkeypatch, tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"
    monkeypatch.setenv("ORTHO4XP_ROOT", str(missing_root))
    result = check_ortho4xp_version(None, {})
    assert result.status == "error"
    monkeypatch.delenv("ORTHO4XP_ROOT", raising=False)


def test_check_ortho4xp_version_missing_from_tool_paths(tmp_path: Path) -> None:
    script = tmp_path / "missing.py"
    result = check_ortho4xp_version(None, {"ortho4xp": script})
    assert result.status == "error"


def test_check_ortho4xp_version_unknown_version(tmp_path: Path) -> None:
    script = tmp_path / "Ortho4XP.py"
    script.write_text("pass", encoding="utf-8")
    result = check_ortho4xp_version(None, {"ortho4xp": script})
    assert result.status == "warn"


def test_check_command_missing() -> None:
    result = check_command("missing", ["definitely_missing_binary"])
    assert result.status == "error"


def test_check_command_nonzero(tmp_path) -> None:
    script = tmp_path / "fail.py"
    script.write_text(
        "import sys\nif '--help' in sys.argv: sys.exit(2)\n",
        encoding="utf-8",
    )
    result = check_command("stub", [sys.executable, str(script)])
    assert result.status == "warn"


def test_check_command_ok(tmp_path) -> None:
    script = tmp_path / "ok.py"
    script.write_text(
        "import sys\nif '--help' in sys.argv: sys.exit(0)\n",
        encoding="utf-8",
    )
    result = check_command("stub", [sys.executable, str(script)])
    assert result.status == "ok"


def test_check_command_preserves_command_list(monkeypatch) -> None:
    captured = {}

    def fake_run(command, **_kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("dem2dsf.doctor.subprocess.run", fake_run)
    monkeypatch.setattr("dem2dsf.doctor.shutil.which", lambda *_: "/bin/echo")
    result = check_command("stub", ["echo", "--flag"])
    assert result.status == "ok"
    assert captured["command"] == ["echo", "--flag", "--help"]


def test_check_command_accepts_string(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.doctor.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )
    monkeypatch.setattr("dem2dsf.doctor.shutil.which", lambda *_: "/bin/echo")
    result = check_command("stub", "echo")
    assert result.status == "ok"


def test_check_command_oserror(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr("dem2dsf.doctor.subprocess.run", boom)
    result = check_command("stub", [sys.executable])
    assert result.status == "error"


def test_check_ortho4xp_python_runner_missing() -> None:
    result = check_ortho4xp_python(None)
    assert result.status == "warn"


def test_check_ortho4xp_python_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.doctor.probe_python_runtime",
        lambda *_: (None, None, "boom"),
    )
    result = check_ortho4xp_python(["runner"])
    assert result.status == "error"


def test_check_ortho4xp_python_missing_version(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.doctor.probe_python_runtime",
        lambda *_: ("/bin/python", None, None),
    )
    result = check_ortho4xp_python(["runner"])
    assert result.status == "warn"


def test_check_ortho4xp_python_warns_on_python2(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.doctor.probe_python_runtime",
        lambda *_: ("/bin/python", (2, 7, 18), None),
    )
    result = check_ortho4xp_python(["runner"])
    assert result.status == "warn"


def test_check_ortho4xp_python_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.doctor.probe_python_runtime",
        lambda *_: ("/bin/python3", (3, 10, 1), None),
    )
    result = check_ortho4xp_python(["runner", "--python", "python3"])
    assert result.status == "ok"


def test_check_ortho4xp_python_ok_no_flag(monkeypatch) -> None:
    monkeypatch.setattr(
        "dem2dsf.doctor.probe_python_runtime",
        lambda *_: ("/bin/python3", (3, 10, 1), None),
    )
    result = check_ortho4xp_python(["runner"])
    assert result.status == "ok"


def test_check_overlay_source_missing_root() -> None:
    result = check_overlay_source(None, {})
    assert result.status == "warn"


def test_check_overlay_source_missing_config(tmp_path: Path) -> None:
    runner = ["runner", "--ortho-root", str(tmp_path)]
    result = check_overlay_source(runner, {})
    assert result.status == "warn"


def test_check_overlay_source_invalid_path(tmp_path: Path) -> None:
    config = tmp_path / "Ortho4XP.cfg"
    config.write_text("custom_overlay_src=missing\n", encoding="utf-8")
    runner = ["runner", "--ortho-root", str(tmp_path)]
    result = check_overlay_source(runner, {})
    assert result.status == "error"


def test_check_overlay_source_ok(tmp_path: Path) -> None:
    overlay_root = tmp_path / "Global Scenery"
    (overlay_root / "Earth nav data").mkdir(parents=True)
    config = tmp_path / "Ortho4XP.cfg"
    config.write_text(f"custom_overlay_src={overlay_root}\n", encoding="utf-8")
    runner = ["runner", "--ortho-root", str(tmp_path)]
    result = check_overlay_source(runner, {})
    assert result.status == "ok"


def test_check_python_version_error(monkeypatch) -> None:
    monkeypatch.setattr("dem2dsf.doctor.sys.version_info", (3, 12))
    result = check_python_version()
    assert result.status == "error"
