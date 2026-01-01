# 7z-compressed DSFs (how they affect DSFTool workflows)

## X‑Plane and 7z DSF compression

Laminar’s DSF usage documentation states:

- Starting with **X‑Plane 10**, the sim can read **7z-compressed DSF files** natively.
- The DSF is stored inside a 7z archive (the sim installs them without decompressing to save disk space).
- 7z compression is **optional**.

Source: https://developer.x-plane.com/article/dsf-usage-in-x-plane/ (DSF Compression section)

## DSFTool behavior over time

From DSFTool release notes (`README.dsf2text` in XPTools):

- 2.0.1 (2015): added an error message hint that a file might be 7‑zipped
- 2.2 b1 (2020): DSFTool became capable of **directly reading 7z-compressed DSF files**

Source: https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

A developer blog post announcing beta builds in 2020 also calls out that DSFTool can directly open 7z-compressed DSFs:

- https://developer.x-plane.com/2020/09/command-line-tools-beta-builds/

## Practical guidance

1. **Know your DSFTool version.**  
   If you need to process global scenery DSFs that are 7z-compressed, use a DSFTool build new enough to read them directly, or decompress first.

2. **For maximum compatibility**, decompress DSFs before feeding them to older DSFTool builds.

3. **If you see errors opening DSFs**, consider:
   - the DSF is 7z-compressed
   - or the DSF uses newer mesh vertex layouts (see 7‑plane vertex support notes)

