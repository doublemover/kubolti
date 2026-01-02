# Windows Quickstart

## Prereqs
- Python 3.13
- Git
- (Optional) 7-Zip for DSF compression

## Install (venv)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Install (pipx)
```powershell
pipx install .
```

## Tool setup
```powershell
python scripts\install_tools.py --write-config
```

This writes `tools\tool_paths.json` and the CLI will auto-detect it. Override with
`$env:DEM2DSF_TOOL_PATHS` if needed.

## Verify
```powershell
dem2dsf doctor
```
