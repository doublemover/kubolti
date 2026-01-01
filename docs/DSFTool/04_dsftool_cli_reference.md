# DSFTool CLI reference (practical)

This is a *practical* reference (not exhaustive) based on the DSFTool README shipped with XPTools and observed binary strings.

## Convert DSF → text

```bash
DSFTool --dsf2text input.dsf output.txt
```

The README also documents converting **multiple DSFs at once** to produce a merged text stream with re-indexed definitions:

```bash
DSFTool --dsf2text A.dsf B.dsf merged.txt
```

(See `08_merging_dsfs.md`.)

## Convert text → DSF

```bash
DSFTool --text2dsf input.txt output.dsf
```

### Piping

For the *text file* parameter, you can use `-` to read/write text via stdin/stdout:

```bash
cat file.txt | DSFTool --text2dsf - out.dsf
DSFTool --dsf2text in.dsf - | grep OBJECT_DEF | wc -l
```

Notes from the README:

- Piping is **not** available for DSF binary output.
- When converting DSF→text, DSFTool sends messages to **stderr** so stdout stays clean for piping.
- Exit codes reflect success/failure.

## Version flag

Recent builds include a `--version` option:

```bash
DSFTool --version
```

## Legacy single-dash flags

DSFTool historically accepted `-dsf2text` / `-text2dsf`. Newer builds still support the single-dash form for backward compatibility.

## XGrinder drag & drop behavior

XGrinder uses suffix to decide conversion:

- `.dsf` → text (DSF2Text)
- `.txt` → DSF

To work with XGrinder, DSFTool must be placed in a `tools/` folder next to the XGrinder executable.

## Performance expectations

The README explicitly warns that text → DSF conversions can take minutes and the tool may appear unresponsive while CPU usage is high.

## Line endings

The README warns that wrong line endings (e.g., from some macOS editors) can crash DSFTool. Prefer UTF‑8 text and Unix LF line endings.

## Sources

- DSFTool README / release notes (XPTools 24‑5 contains `README.dsf2text`):  
  https://files.x-plane.com/public/xptools/xptools_win_24-5.zip

- XPTools download page:  
  https://developer.x-plane.com/tools/xptools/

