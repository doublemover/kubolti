"""Wrapper utilities for running DSFTool."""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from dem2dsf.subprocess_utils import run_command
DSF_7Z_SIGNATURE = b"\x37\x7a\xbc\xaf\x27\x1c"
MIN_7Z_VERSION = (2, 2, 0)
VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass(frozen=True)
class DsftoolResult:
    """Captured output from a DSFTool invocation."""

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
    """Build the DSFTool command line, handling Python scripts."""
    command = _normalize_tool_cmd(tool_cmd)
    if not command:
        raise ValueError("DSFTool command is required.")
    tool_token = command[-1]
    if Path(tool_token).suffix.lower() == ".py" and not _has_python_exe(command[:-1]):
        command = [*command[:-1], sys.executable, tool_token]
    return [*command, *args]


def run_dsftool(
    tool_cmd: Sequence[str] | Path | str,
    args: list[str],
    *,
    timeout: float | None = None,
    retries: int = 0,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
) -> DsftoolResult:
    """Run DSFTool and capture stdout/stderr."""
    command = _build_command(tool_cmd, args)
    attempts = max(0, int(retries))
    result = None
    for attempt in range(attempts + 1):
        result = run_command(
            command,
            timeout=timeout,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if result.returncode == 0:
            break
        if attempt >= attempts:
            break
    if result is None:  # pragma: no cover - defensive guard
        result = run_command(command, timeout=timeout)
    return DsftoolResult(
        command=result.command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def dsftool_version(tool_cmd: Sequence[str] | Path | str) -> tuple[int, int, int] | None:
    """Return DSFTool version tuple if available."""
    result = run_dsftool(tool_cmd, ["--version"])
    if result.returncode != 0:
        return None
    output = f"{result.stdout}\n{result.stderr}".strip()
    match = VERSION_PATTERN.search(output)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return (major, minor, patch)


def dsf_is_7z(path: Path) -> bool:
    """Return True if the DSF file appears to be 7z-compressed."""
    try:
        with path.open("rb") as handle:
            header = handle.read(len(DSF_7Z_SIGNATURE))
    except OSError:
        return False
    return header == DSF_7Z_SIGNATURE


def dsftool_7z_hint(tool_cmd: Sequence[str] | Path | str, dsf_path: Path) -> str | None:
    if not dsf_is_7z(dsf_path):
        return None
    version = dsftool_version(tool_cmd)
    if version is None:
        return "DSF appears 7z-compressed; use DSFTool 2.2+ or decompress first"
    if version < MIN_7Z_VERSION:
        version_str = ".".join(str(part) for part in version[:2])
        return (
            f"DSFTool {version_str} cannot read 7z-compressed DSFs; "
            "use 2.2+ or decompress first"
        )
    return None


def dsf_to_text(
    tool_cmd: Sequence[str] | Path | str,
    dsf_path: Path,
    text_path: Path,
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> None:
    """Convert a DSF file to text with DSFTool."""
    hint = dsftool_7z_hint(tool_cmd, dsf_path)
    if hint and "cannot read" in hint:
        raise RuntimeError(f"DSFTool dsf2text failed: {hint}")

    result = run_dsftool(
        tool_cmd,
        ["--dsf2text", str(dsf_path), str(text_path)],
        timeout=timeout,
        retries=retries,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "unknown error"
        if hint:
            message = f"{message} ({hint})"
        raise RuntimeError(f"DSFTool dsf2text failed: {message}")


def roundtrip_dsf(
    tool_cmd: Sequence[str] | Path | str,
    dsf_path: Path,
    work_dir: Path,
    *,
    timeout: float | None = None,
    retries: int = 0,
) -> None:
    """Convert DSF to text and back as a structural smoke test."""
    text_path = work_dir / f"{dsf_path.stem}.txt"
    rebuilt_path = work_dir / dsf_path.name

    hint = dsftool_7z_hint(tool_cmd, dsf_path)
    if hint and "cannot read" in hint:
        raise RuntimeError(f"DSFTool dsf2text failed: {hint}")

    result = run_dsftool(
        tool_cmd,
        ["--dsf2text", str(dsf_path), str(text_path)],
        timeout=timeout,
        retries=retries,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "unknown error"
        if hint:
            message = f"{message} ({hint})"
        raise RuntimeError(f"DSFTool dsf2text failed: {message}")

    result = run_dsftool(
        tool_cmd,
        ["--text2dsf", str(text_path), str(rebuilt_path)],
        timeout=timeout,
        retries=retries,
    )
    if result.returncode != 0:
        raise RuntimeError(f"DSFTool text2dsf failed: {result.stderr.strip()}")
