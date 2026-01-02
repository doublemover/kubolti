from __future__ import annotations

import sys
import textwrap

from dem2dsf.tools.dsftool import (
    _build_command,
    dsf_is_7z,
    dsftool_version,
    roundtrip_dsf,
    run_dsftool,
)


def test_roundtrip_dsf(tmp_path) -> None:
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        textwrap.dedent(
            """
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            if "--dsf2text" in args:
                out_path = Path(args[-1])
                out_path.write_text("text", encoding="utf-8")
            elif "--text2dsf" in args:
                out_path = Path(args[-1])
                out_path.write_text("dsf", encoding="utf-8")
            else:
                sys.exit(1)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_text("dsf", encoding="utf-8")

    roundtrip_dsf([str(tool)], dsf_path, tmp_path)

    assert (tmp_path / "tile.txt").exists()
    assert (tmp_path / "tile.dsf").exists()


def test_roundtrip_dsf_raises(tmp_path) -> None:
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import sys\nif '--dsf2text' in sys.argv: sys.exit(1)\n",
        encoding="utf-8",
    )
    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_text("dsf", encoding="utf-8")

    try:
        roundtrip_dsf([str(tool)], dsf_path, tmp_path)
    except RuntimeError as exc:
        assert "dsf2text failed" in str(exc)
    else:
        raise AssertionError("Expected dsf2text failure")


def test_roundtrip_dsf_7z_requires_newer_version(tmp_path) -> None:
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import sys\nif '--version' in sys.argv:\n    print('DSFTool 2.1')\n    sys.exit(0)\n",
        encoding="utf-8",
    )
    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_bytes(b"\x37\x7a\xbc\xaf\x27\x1c" + b"payload")

    try:
        roundtrip_dsf([str(tool)], dsf_path, tmp_path)
    except RuntimeError as exc:
        assert "dsf2text failed" in str(exc)
        assert "2.2" in str(exc)
    else:
        raise AssertionError("Expected dsf2text failure")


def test_build_command_non_py() -> None:
    command = _build_command(["dsftool"], ["--help"])
    assert command[0].endswith("dsftool")


def test_build_command_inserts_python_for_py_wrapper() -> None:
    command = _build_command(["conda", "run", "dsftool.py"], ["--help"])
    assert command[:2] == ["conda", "run"]
    assert command[2] == sys.executable
    assert command[3].endswith("dsftool.py")


def test_run_dsftool_non_py(tmp_path) -> None:
    if sys.platform.startswith("win"):
        tool = tmp_path / "dsftool.cmd"
        tool.write_text("@echo ok\n", encoding="utf-8")
    else:
        tool = tmp_path / "dsftool.sh"
        tool.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
        tool.chmod(0o755)
    result = run_dsftool([str(tool)], ["--help"])
    assert result.command[0].endswith(tool.name)


def test_dsftool_version_parses_output(tmp_path) -> None:
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('DSFTool 2.4a1')\n"
        "    sys.exit(0)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    assert dsftool_version([str(tool)]) == (2, 4, 0)


def test_dsf_is_7z(tmp_path) -> None:
    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_bytes(b"\x37\x7a\xbc\xaf\x27\x1c" + b"payload")
    assert dsf_is_7z(dsf_path) is True
