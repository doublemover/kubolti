# Overlay Plugins

Overlay generators let you inject custom overlay outputs. Built-ins include
`drape` (texture swap), `copy` (package existing overlays), and `inventory`
(scan a build for overlay assets).

## Built-in drape
```bash
python -m dem2dsf overlay \
  --build-dir build \
  --output overlay_out \
  --texture textures/new.dds
```

## Built-in copy
Copies `Earth nav data` plus optional `terrain` and `textures`.

```bash
python -m dem2dsf overlay \
  --generator copy \
  --build-dir build \
  --output overlay_copy \
  --tile +47+008 \
  --tile +48+008 \
  --skip-textures
```

## Built-in inventory
Writes `overlay_inventory.json` with DSF paths, terrain files, and texture refs.

```bash
python -m dem2dsf overlay \
  --generator inventory \
  --build-dir build \
  --output overlay_inventory
```

## Plugin interface
Provide a Python file that exposes either `PLUGIN` or a `register(registry)`
function. The plugin object must have a `name` attribute, an
`interface_version` matching `OVERLAY_INTERFACE_VERSION`, and a `generate()`
method that returns `OverlayResult`.

```python
from dem2dsf.overlay import OVERLAY_INTERFACE_VERSION, OverlayResult

class Demo:
    name = "demo"
    interface_version = OVERLAY_INTERFACE_VERSION

    def generate(self, request):
        return OverlayResult(
            generator=self.name,
            artifacts={"ok": True},
            warnings=(),
            errors=(),
        )

PLUGIN = Demo()
```

Invoke with:

```bash
python -m dem2dsf overlay --generator demo --plugin ./demo_plugin.py --output overlay_out
```

## Entrypoints
Overlay generators can be registered via package entrypoints using the group
`dem2dsf.overlays`. Each entrypoint should resolve to a generator instance or a
callable that returns one. The generator name is used by `--generator`.
