"""Wrapper utilities for running DDSTool and validating DDS textures."""
from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from dem2dsf.subprocess_utils import run_command

DDS_SIGNATURE = b"DDS "


@dataclass(frozen=True)
class DdstoolResult:
    """Captured output from a DDSTool invocation."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def _normalize_tool_cmd(tool_cmd: Sequence[str] | Path | str) -> list[str]:
    """Normalize a tool command into a list of strings."""
    if isinstance(tool_cmd, Path):
        return [str(tool_cmd)]
    if isinstance(tool_cmd, str):
        return [tool_cmd]
    return [str(item) for item in tool_cmd]


def _has_python_exe(command: Sequence[str]) -> bool:
    """Return True if a command already invokes a Python interpreter."""
    for token in command:
        name = Path(token).name.lower()
        if name in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}:
            return True
        if name.startswith("python"):
            return True
    return False


def _build_command(tool_cmd: Sequence[str] | Path | str, args: list[str]) -> list[str]:
    """Build the DDSTool command line, handling Python scripts."""
    command = _normalize_tool_cmd(tool_cmd)
    if not command:
        raise ValueError("DDSTool command is required.")
    tool_token = command[-1]
    if Path(tool_token).suffix.lower() == ".py" and not _has_python_exe(command[:-1]):
        command = [*command[:-1], sys.executable, tool_token]
    return [*command, *args]


def run_ddstool(
    tool_cmd: Sequence[str] | Path | str,
    args: list[str],
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> DdstoolResult:
    """Run DDSTool and capture stdout/stderr."""
    command = _build_command(tool_cmd, args)
    attempts = max(0, int(retries))
    result = None
    for attempt in range(attempts + 1):
        result = run_command(command, timeout=timeout)
        if result.returncode == 0:
            break
        if attempt >= attempts:
            break
    if result is None:  # pragma: no cover - defensive guard
        result = run_command(command, timeout=timeout)
    return DdstoolResult(
        command=result.command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def dds_header_ok(path: Path) -> bool:
    """Return True if a DDS file header matches the expected signature."""
    try:
        with path.open("rb") as handle:
            header = handle.read(len(DDS_SIGNATURE))
    except OSError:
        return False
    return header == DDS_SIGNATURE


def ddstool_info(
    tool_cmd: Sequence[str] | Path | str,
    dds_path: Path,
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> None:
    """Run DDSTool in info mode for a DDS file."""
    result = run_ddstool(
        tool_cmd,
        ["--info", str(dds_path)],
        timeout=timeout,
        retries=retries,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"DDSTool failed: {message}")
