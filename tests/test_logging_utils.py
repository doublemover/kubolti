from __future__ import annotations

import json
import logging
from pathlib import Path

from dem2dsf.logging_utils import LogOptions, configure_logging


def test_configure_logging_writes_json(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "dem2dsf.jsonl"
    configure_logging(LogOptions(log_file=log_path))
    logger = logging.getLogger("dem2dsf.test")
    logger.info("hello", extra={"tile": "+47+008"})
    logging.shutdown()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    payload = json.loads(lines[-1])
    assert payload["message"] == "hello"
    assert payload["level"] == "info"
    assert payload["extra"]["tile"] == "+47+008"
