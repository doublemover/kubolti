"""Backend registry for named build adapters."""

from __future__ import annotations

import logging
from functools import lru_cache
from importlib import metadata
from typing import Callable, cast

from dem2dsf.backends.base import Backend
from dem2dsf.backends.ortho4xp import Ortho4XPBackend

BackendFactory = Callable[[], Backend]
BACKEND_ENTRYPOINT_GROUP = "dem2dsf.backends"

LOGGER = logging.getLogger(__name__)

_BUILTIN_BACKENDS: dict[str, BackendFactory] = {
    "ortho4xp": Ortho4XPBackend,
}


def _load_backend_entrypoints() -> dict[str, BackendFactory]:
    """Load backend factories from package entrypoints."""
    factories: dict[str, BackendFactory] = {}
    try:
        entry_points = metadata.entry_points(group=BACKEND_ENTRYPOINT_GROUP)
    except Exception as exc:  # pragma: no cover - entrypoint discovery failures are rare
        LOGGER.warning("Failed to read backend entrypoints: %s", exc)
        return factories
    for entry_point in entry_points:
        try:
            candidate = entry_point.load()
        except Exception as exc:
            LOGGER.warning("Failed to load backend entrypoint '%s': %s", entry_point.name, exc)
            continue
        if not callable(candidate):
            LOGGER.warning("Backend entrypoint '%s' is not callable.", entry_point.name)
            continue
        factories[entry_point.name] = cast(BackendFactory, candidate)
    return factories


@lru_cache(maxsize=1)
def _backend_factories() -> dict[str, BackendFactory]:
    """Return merged backend factories from built-ins and entrypoints."""
    factories = dict(_BUILTIN_BACKENDS)
    for name, factory in _load_backend_entrypoints().items():
        if name in factories:
            LOGGER.warning("Backend '%s' already registered; skipping entrypoint.", name)
            continue
        factories[name] = factory
    return factories


def refresh_backends() -> None:
    """Clear cached backend factories and reload on demand."""
    _backend_factories.cache_clear()


def get_backend(name: str) -> Backend:
    """Return a backend instance for the given name."""
    try:
        backend_factory = _backend_factories()[name]
    except KeyError as exc:
        raise KeyError(f"Unknown backend: {name}") from exc
    try:
        return backend_factory()
    except Exception as exc:  # pragma: no cover - defensive guard for plugin failures
        raise RuntimeError(f"Failed to initialize backend: {name}") from exc


def list_backends() -> dict[str, Backend]:
    """Return a mapping of backend names to instances."""
    backends: dict[str, Backend] = {}
    for name, factory in _backend_factories().items():
        try:
            backends[name] = factory()
        except Exception as exc:
            LOGGER.warning("Skipping backend '%s' because it failed to initialize: %s", name, exc)
    return backends
