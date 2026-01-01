"""Performance timing helpers for builds and benchmarks."""

from __future__ import annotations

import os
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator


@dataclass(frozen=True)
class PerfSpan:
    """Timing span captured by the performance tracker."""

    name: str
    seconds: float


class PerfTracker:
    """Capture timing spans and optional memory peaks."""

    def __init__(self, *, enabled: bool, track_memory: bool = True) -> None:
        self.enabled = enabled
        self.track_memory = track_memory
        self._spans: list[PerfSpan] = []
        self._totals: dict[str, float] = {}
        self._counts: dict[str, int] = {}
        self._start_time: float | None = None
        self._end_time: float | None = None
        self._peak_memory: float | None = None
        self._mem_started = False
        self._mem_was_tracing = False

    def start(self) -> None:
        """Start a timing session."""
        if not self.enabled:
            return
        self._start_time = perf_counter()
        if self.track_memory:
            self._mem_was_tracing = tracemalloc.is_tracing()
            if not self._mem_was_tracing:
                tracemalloc.start()
                self._mem_started = True

    def stop(self) -> None:
        """Stop a timing session and capture memory usage."""
        if not self.enabled or self._end_time is not None:
            return
        self._end_time = perf_counter()
        if self.track_memory and tracemalloc.is_tracing():
            _, peak = tracemalloc.get_traced_memory()
            self._peak_memory = peak / (1024 * 1024)
            if self._mem_started and not self._mem_was_tracing:
                tracemalloc.stop()

    @contextmanager
    def span(self, name: str) -> Iterator[None]:
        """Measure a named span of work."""
        if not self.enabled:
            yield
            return
        start = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - start
            self._spans.append(PerfSpan(name=name, seconds=elapsed))
            self._totals[name] = self._totals.get(name, 0.0) + elapsed
            self._counts[name] = self._counts.get(name, 0) + 1

    def summary(self) -> dict[str, Any]:
        """Return a JSON-serializable summary of captured metrics."""
        if not self.enabled:
            return {}
        total_seconds = 0.0
        if self._start_time is not None and self._end_time is not None:
            total_seconds = max(0.0, self._end_time - self._start_time)
        spans = {
            name: {
                "seconds": round(total, 6),
                "count": self._counts.get(name, 0),
            }
            for name, total in sorted(self._totals.items())
        }
        events = [
            {"name": span.name, "seconds": round(span.seconds, 6)}
            for span in self._spans
        ]
        summary = {
            "total_seconds": round(total_seconds, 6),
            "spans": spans,
            "events": events,
        }
        if self._peak_memory is not None:
            summary["peak_memory_mb"] = round(self._peak_memory, 3)
        return summary


def resolve_metrics_path(
    output_dir: Path, metrics_json: str | None
) -> Path | None:
    """Resolve the metrics output path from CLI or environment defaults."""
    if metrics_json:
        return Path(metrics_json)
    profile_dir = os.environ.get("DEM2DSF_PROFILE_DIR")
    if profile_dir:
        return Path(profile_dir) / "build_metrics.json"
    return None
