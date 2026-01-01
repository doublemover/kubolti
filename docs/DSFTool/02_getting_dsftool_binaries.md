# Getting DSFTool binaries (XPTools downloads)

## Official downloads

Laminar publishes DSFTool as part of **XPTools** (“Command‑Line Tools”) with builds for Windows, macOS, and Linux.

Current downloads are listed here:

- https://developer.x-plane.com/tools/xptools/

The same page also links older releases.

## What the Windows zip contains (example: XPTools 24‑5)

The Windows archive linked on the XPTools page contains:

- `tools/DSFTool.exe`
- README files including `README.dsf2text` (DSFTool instructions/release notes)
- `XGrinder.exe` (drag‑and‑drop front-end)
- other tools (DDSTool, ObjView, etc.)

Example download (Windows):

- https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

(Your macOS/Linux file names differ but the layout is conceptually similar.)

## Installing for XGrinder

If you use **XGrinder**, DSFTool must be in a subdirectory named `tools` located next to XGrinder, e.g.:

```
XGrinder.exe
tools/
  DSFTool.exe
  DDSTool.exe
  ...
```

This is called out in the DSFTool README.

## Verifying the DSFTool version

Recent binaries include `--version` (and older single-dash forms like `-text2dsf` remain supported for backward compatibility).

You can typically run:

```bash
DSFTool --version
```

(Exact output format can vary by build.)

The `README.dsf2text` shipped in XPTools 24‑5 includes DSFTool release notes through **2.4 a1 (May 2024)**.

## Sources

- XPTools downloads (official):  
  https://developer.x-plane.com/tools/xptools/

- XPTools 24‑5 Windows zip (contains DSFTool + README.dsf2text):  
  https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

