# Building DSFTool from source (XPTools)

DSFTool’s source code lives in the **XPTools** repository (Laminar Research).

Laminar’s build notes are here:

- https://developer.x-plane.com/code/

## High-level steps (all platforms)

1. Install a suitable compiler/toolchain for your OS.
2. Install **CMake** (macOS) and toolchain prerequisites (Linux/Windows).
3. Clone the XPTools repo *with submodules*:
   ```bash
   git clone --recurse-submodules https://github.com/X-Plane/xptools.git
   ```
4. Build the tools (varies by platform; see below).
5. Find built artifacts under:
   ```
   [xptools dir]/build/[platform]/[configuration]
   ```

## macOS notes (from Laminar)

Laminar’s guide calls out:

- macOS 10.12+ and the newest supported Xcode
- install CMake, e.g. via Homebrew:
  ```bash
  brew install cmake
  ```

## Windows notes (from Laminar)

Two main options are described:

- **Visual Studio 2017+** for modern WED/tool builds (recommended)
- **MinGW** mainly for older workflows

A key warning in the guide:

- Avoid **spaces in paths** in some MinGW/makefile workflows.

## Linux / MinGW prerequisites (from Laminar)

The developer page lists common prerequisites such as:

- development packages for `libbfd` (binutils), `libmpfr`, `libz`, `boost`
- `gcc 7`
- `gnu make`

Then build with:

```bash
make -j
```

## Why build from source?

Typical reasons:

- You need a DSFTool feature not present in your platform’s latest binary package yet.
- You want to patch DSFTool behavior (e.g., raster handling edge cases).
- You want to contribute fixes upstream.

## Sources

- Scenery tools build instructions:  
  https://developer.x-plane.com/code/

- XPTools repository (source):  
  https://github.com/X-Plane/xptools

