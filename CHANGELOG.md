# Changelog

All notable changes to this project are documented in this file.

## [0.1.1] - 2026-01-01

### Added
- Build config schema and locked config outputs to make builds reproducible.
- AOI mask and tile inference support, including CRS handling and validation tests.
- Clean command and cache helpers for build artifacts and diagnostics bundles.
- Provenance reporting with pinned version checks for key dependencies/tools.
- DDSTool validation support alongside DSFTool validation modes.
- Ortho4XP entrypoint integration checks and richer runner logging outputs.
- GUI preferences persistence plus GUI smoke/build scripts.
- Performance profiling/benchmarking scripts and CI perf smoke runs.
- Documentation quickstarts (Windows/macOS/Linux), security posture, compatibility, and tool paths template.

### Changed
- XPTools installs now use platform zip bundles with clearer DSFTool/DDSTool discovery.
- External tool detection prefers platform-native binaries and caches tool downloads in CI.
- CLI workflows expanded (wizard, autoortho, publish) with more structured output artifacts.

### Fixed
- Resume/config flow and validate-only behavior.
- DSFTool discovery on macOS/arm and executable permission handling after extraction.
- README formatting and usage guide consistency.

### Docs
- Expanded DSFTool and Ortho4XP references, output layout notes, and migration guidance.
