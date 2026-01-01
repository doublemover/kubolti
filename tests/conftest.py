from __future__ import annotations

import pytest

from dem2dsf.tools import config as tool_config


def pytest_collection_modifyitems(config, items) -> None:
    """Skip integration tests unless explicitly selected via -m integration."""
    markexpr = config.option.markexpr or ""
    if "integration" in markexpr:
        return
    skip_integration = pytest.mark.skip(reason="integration tests run only with -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def _isolate_tool_paths(monkeypatch, tmp_path) -> None:
    """Prevent local tool configs from bleeding into tests."""
    monkeypatch.setenv(tool_config.ENV_TOOL_PATHS, str(tmp_path / "missing_tool_paths.json"))
