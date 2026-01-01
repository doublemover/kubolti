"""Subprocess helpers with optional log streaming and retries."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class CommandResult:
    """Captured output from a command invocation."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    stdout_path: Path | None
    stderr_path: Path | None
    timed_out: bool


def _tail_text(path: Path, *, max_bytes: int = 65536, max_lines: int = 200) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            data = handle.read()
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines)


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    tail_bytes: int = 65536,
    tail_lines: int = 200,
) -> CommandResult:
    """Run a command, optionally streaming output to log files."""
    cmd_list = [str(item) for item in command]
    timed_out = False
    if stdout_path or stderr_path:
        stdout_handle = (
            stdout_path.open("w", encoding="utf-8") if stdout_path else subprocess.DEVNULL
        )
        stderr_handle = (
            stderr_path.open("w", encoding="utf-8") if stderr_path else subprocess.DEVNULL
        )
        try:
            result = subprocess.run(
                cmd_list,
                cwd=cwd,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            result = subprocess.CompletedProcess(cmd_list, 124, "", "")
        finally:
            if stdout_path:
                stdout_handle.close()
            if stderr_path:
                stderr_handle.close()
        stdout = _tail_text(stdout_path, max_bytes=tail_bytes, max_lines=tail_lines)
        stderr = _tail_text(stderr_path, max_bytes=tail_bytes, max_lines=tail_lines)
        if timed_out:
            timeout_message = f"Command timed out after {timeout} seconds."
            stderr = f"{stderr}\n{timeout_message}" if stderr else timeout_message
        return CommandResult(
            cmd_list,
            result.returncode,
            stdout,
            stderr,
            stdout_path,
            stderr_path,
            timed_out,
        )

    try:
        result = subprocess.run(
            cmd_list,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return CommandResult(
            cmd_list,
            result.returncode,
            result.stdout,
            result.stderr,
            None,
            None,
            False,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        timeout_message = f"Command timed out after {timeout} seconds."
        stderr = f"{stderr}\n{timeout_message}" if stderr else timeout_message
        return CommandResult(
            cmd_list,
            124,
            stdout,
            stderr,
            None,
            None,
            timed_out,
        )
