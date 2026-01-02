# macOS Quickstart

## Prereqs
- Python 3.13
- Git
- (Optional) 7-Zip (`brew install p7zip`)

## Install (venv)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Install (pipx)
```bash
pipx install .
```

## Tool setup
```bash
python scripts/install_tools.py --write-config
```

This writes `tools/tool_paths.json` and the CLI will auto-detect it. Override with
`DEM2DSF_TOOL_PATHS` if needed.

## Verify
```bash
dem2dsf doctor
```
