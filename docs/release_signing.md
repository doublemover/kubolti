# Release Packaging and Signing

This repo ships signed artifacts when a signing key is available. Releases build wheels and sdists, then optionally sign them with GPG.

## Requirements
- Python 3.13
- `build` (`python -m pip install build`)
- GPG (optional for signing)

## Local release workflow
1) Build artifacts:
   - `python scripts/build_release.py`
2) Sign artifacts (optional):
   - `python scripts/sign_release.py`
3) Build GUI bundles (optional):
   - `python scripts/build_gui.py --output-dir dist/gui --name dem2dsf-gui --onedir`

Artifacts are written to `dist/` and signatures are saved as `*.asc` files next to them.

## CI signing
The GitHub Actions workflow `release.yml` signs artifacts if secrets are present:
- `GPG_PRIVATE_KEY` (ASCII-armored private key)
- `GPG_PASSPHRASE` (optional)

Without these secrets, the workflow still produces unsigned artifacts and publishes them to the release.
The release workflow also builds GUI bundles for Linux, macOS, and Windows and attaches them to tagged releases.

## Tool discovery on clean systems
Run `python scripts/install_tools.py --write-config` to generate `tools/tool_paths.json`.
The CLI auto-loads this file (or you can set `DEM2DSF_TOOL_PATHS` to point at it)
to discover Ortho4XP, DSFTool, and 7-Zip automatically.
Releases assume Ortho4XP is installed separately; dem2dsf no longer supports MeshTool.
