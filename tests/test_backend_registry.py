from __future__ import annotations

from dem2dsf import contracts
from dem2dsf.backends.base import BackendSpec, BuildRequest, BuildResult
from dem2dsf.backends.ortho4xp import Ortho4XPBackend
from dem2dsf.backends.registry import list_backends, refresh_backends


class DummyBackend:
    def spec(self) -> BackendSpec:
        return BackendSpec(
            name="dummy",
            version="0.1",
            artifact_schema_version=contracts.SCHEMA_VERSION,
            tile_dem_crs="EPSG:4326",
            supports_xp12_rasters=False,
            supports_autoortho=False,
        )

    def build(self, request: BuildRequest) -> BuildResult:
        return BuildResult(build_plan={}, build_report={})


def test_backend_entrypoints(monkeypatch) -> None:
    class DummyEntryPoint:
        name = "dummy"

        def load(self):
            return DummyBackend

    refresh_backends()
    monkeypatch.setattr(
        "dem2dsf.backends.registry.metadata.entry_points",
        lambda group: [DummyEntryPoint()],
    )

    backends = list_backends()
    assert "dummy" in backends
    refresh_backends()


def test_backend_entrypoint_duplicate_skipped(monkeypatch) -> None:
    class DuplicateEntryPoint:
        name = "ortho4xp"

        def load(self):
            return DummyBackend

    refresh_backends()
    monkeypatch.setattr(
        "dem2dsf.backends.registry.metadata.entry_points",
        lambda group: [DuplicateEntryPoint()],
    )

    backends = list_backends()
    assert isinstance(backends["ortho4xp"], Ortho4XPBackend)
    refresh_backends()
