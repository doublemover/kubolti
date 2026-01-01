"""Backend registry for named build adapters."""

from __future__ import annotations

from typing import Dict, Type

from dem2dsf.backends.base import Backend
from dem2dsf.backends.ortho4xp import Ortho4XPBackend

_BACKEND_FACTORIES: Dict[str, Type[Backend]] = {
    "ortho4xp": Ortho4XPBackend,
}


def get_backend(name: str) -> Backend:
    """Return a backend instance for the given name."""
    try:
        backend_type = _BACKEND_FACTORIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown backend: {name}") from exc
    return backend_type()


def list_backends() -> Dict[str, Backend]:
    """Return a mapping of backend names to instances."""
    return {name: backend_type() for name, backend_type in _BACKEND_FACTORIES.items()}
