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
function. The plugin object must have a `name` attribute and a `generate()`
method that returns `OverlayResult`.

```python
from dem2dsf.overlay import OverlayResult

class Demo:
    name = "demo"

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
