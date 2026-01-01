# What DSFTool is (and isn’t)

## What it is

**DSFTool** is a command‑line utility from Laminar Research’s **XPTools** bundle that converts X‑Plane **DSF (Distribution Scenery Format)** files to a text representation (commonly called **DSF2Text**) and back again.

Practical uses:

- **Inspection / debugging** of DSF contents (objects, polygons, networks, rasters, mesh patches).
- **Programmatic generation** of overlays or base meshes by emitting DSF2Text + sidecar raster files and compiling them to DSF.
- **Round‑trip editing** workflows (DSF → text → automated edits → DSF).

Official docs consistently frame DSFTool/DSF2Text as a low-level building block for **toolchains**, not a “human editor.”  
Ben Supnik described DSF2Text as “a link in a chain of scenery editing tools,” primarily for programmers feeding generated text into the converter. (See: “DSF2Text – Just a Link in the Chain”.)

## What it isn’t

- A convenient manual editor for large DSFs (editing multi‑MB text files by hand is error‑prone and slow).
- A full scenery authoring environment (Laminar expects most authors to use higher-level tools such as **WED** for airports/overlays and **MeshTool** for mesh generation).
- A perfect reflection of DSF internals: DSFTool’s text format intentionally hides many binary DSF compression concepts (e.g., point pools).

## Where DSFTool fits in the X‑Plane scenery ecosystem

A typical “low-level” pipeline looks like:

1. **Generate / modify** DSF2Text + raster RAW sidecars (your program).
2. **Compile** to DSF with DSFTool.
3. **Validate / inspect** by converting back to text and diffing key structures.
4. **Run in X‑Plane** and verify visual/physics correctness.

DSFTool is included in **XPTools** alongside utilities like DDSTool and XGrinder (GUI drag‑and‑drop front-end).

## Key practical expectations (from tool release notes)

- DSFTool can be **slow** converting text back to DSF (minutes in some cases).
- There are known **workflow gotchas** like line endings issues on macOS editors.
- New DSFTool builds have historically tracked new DSF features (e.g., raster layers for X‑Plane 10, 7z support, AGL/7-plane vertices for modern sceneries).

## Sources

- DSF2Text purpose statement (“link in the chain”):  
  https://developer.x-plane.com/2005/12/dsf2text-just-a-link-in-the-chain/

- DSFTool overview and warnings (release notes README.dsf2text included in XPTools 24‑5 download):  
  https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

- XPTools overview/downloads:  
  https://developer.x-plane.com/tools/xptools/

