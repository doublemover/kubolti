"""Logging helpers for dem2dsf CLI and tools."""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LogOptions:
    """Configuration for logging output."""

    verbose: int = 0
    quiet: bool = False
    log_file: Path | None = None
    json_console: bool = False


def _timestamp() -> str:
    """Return the current UTC timestamp in ISO8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Return non-standard LogRecord fields for JSON logging."""
    reserved = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
    }
    return {key: value for key, value in record.__dict__.items() if key not in reserved}


class JsonFormatter(logging.Formatter):
    """Format log records as JSON objects (one per line)."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record into JSON text."""
        payload: dict[str, Any] = {
            "timestamp": _timestamp(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = _extra_fields(record)
        if extra:
            payload["extra"] = extra
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


class HumanFormatter(logging.Formatter):
    """Format log records with a concise, human readable prefix."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with optional tile context."""
        message = super().format(record)
        tile = getattr(record, "tile", None)
        if tile:
            return f"[{tile}] {message}"
        return message


def _resolve_level(options: LogOptions) -> int:
    """Resolve the log level for console output."""
    if options.quiet:
        return logging.WARNING
    if options.verbose > 0:
        return logging.DEBUG
    return logging.INFO


def configure_logging(options: LogOptions) -> logging.Logger:
    """Configure logging based on LogOptions and return the root logger."""
    level = _resolve_level(options)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_formatter: logging.Formatter
    if options.json_console:
        console_formatter = JsonFormatter()
    else:
        console_formatter = HumanFormatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    root.addHandler(console_handler)

    if options.log_file:
        options.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(options.log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)

    return root
