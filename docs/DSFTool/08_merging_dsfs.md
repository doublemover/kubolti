# Merging DSFs via DSFTool (practical workflow)

DSFTool includes a **merge helper** workflow when converting DSF→text.

## What DSFTool does

If you provide **multiple input DSFs** in `--dsf2text` mode, DSFTool will:

- emit DSF2Text for all of them into one output stream, and
- automatically **offset definition indexes** (OBJECT_DEF, POLYGON_DEF, etc.) in the later files so that the combined text is internally consistent.

This makes it possible to manually (or programmatically) consolidate the text and compile it back into a single DSF.

Source: DSFTool README (`README.dsf2text` in XPTools)

## Typical steps

1. Convert both DSFs to one text file:

   ```bash
   DSFTool --dsf2text A.dsf B.dsf merged.txt
   ```

2. In `merged.txt`, consolidate **properties**:
   - each DSF contributes its own properties
   - you’ll get duplicates
   - keep the correct `sim/west/south/east/north` bounds for the final tile
   - keep `sim/overlay` if you’re producing an overlay

3. Compile back to DSF:

   ```bash
   DSFTool --text2dsf merged.txt merged.dsf
   ```

## Indexing tip (object loading priority)

The DSFTool README notes that the `sim/require_object` property can force objects of a given index and higher to always load. Therefore, when merging DSFs that mix autogen-like objects with custom scenery, place the **custom scenery second** so its objects end up with higher indexes.

(Exact property names/semantics are documented in the DSF usage spec.)

## Sources

- DSFTool README / merge section (`README.dsf2text`):  
  https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

- DSF properties (require_object, require_facade, etc.):  
  https://developer.x-plane.com/article/dsf-usage-in-x-plane/

