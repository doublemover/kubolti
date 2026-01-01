# X-Plane XPTools (Command-Line Tools)

Source: https://developer.x-plane.com/tools/xptools/

## Why it matters
XPTools includes DSFTool, which is the canonical DSF text round-trip and validation utility used in the pipeline.

## Key points
- DSFTool converts DSF binary to text and back; useful for smoke tests and property checks.
- DDSTool converts PNG to DDS; relevant when handling terrain textures.
- ObjView is a simple OBJ viewer; XGrinder is a drag-and-drop front end for DSFTool and DDSTool.
- Releases are labeled by year and month (for example, 24-5); download platform-specific builds.
- DSFTool 2.2+ is required to read 7z-compressed DSFs directly.

## Latest downloads (from tools page)
- Windows: https://files.x-plane.com/public/xptools/xptools_win_24-5.zip
- macOS: https://files.x-plane.com/public/xptools/xptools_mac_24-5.zip
- Linux: https://files.x-plane.com/public/xptools/xptools_lin_24-5.zip

## Binaries (used by this project)
- Download the platform zip and point `scripts/install_tools.py` at it.
- The zip includes `tools/DSFTool.exe`, `tools/DDSTool.exe`, and `README.dsf2text`.
