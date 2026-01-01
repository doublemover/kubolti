from __future__ import annotations

import pytest

from dem2dsf.backends.registry import get_backend, list_backends


def test_get_backend_unknown() -> None:
    with pytest.raises(KeyError, match="Unknown backend"):
        get_backend("missing")


def test_list_backends_includes_defaults() -> None:
    backends = list_backends()
    assert "ortho4xp" in backends
