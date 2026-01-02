# Security posture

## Downloads and trust
- Tool downloads are only attempted when you run `scripts/install_tools.py`.
- dem2dsf treats URLs you provide as trusted. Use official sources for Ortho4XP and XPTools.

## Archive extraction safety
- Archives are extracted with a path traversal guard (`_safe_extract_path`).
- Any archive member that escapes the destination is rejected.

## Execution
- External tools run as your user. Keep them in trusted locations and avoid untrusted binaries.
- Publish packaging only reads from your build directory and writes the output zip.
