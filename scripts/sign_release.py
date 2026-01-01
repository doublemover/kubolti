"""Sign release artifacts in dist/ using GPG."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _gpg_binary() -> str | None:
    """Return the gpg binary path if available."""
    return os.environ.get("GPG") or shutil.which("gpg")


def main() -> int:
    """Sign files in dist/ with GPG and emit .asc signatures."""
    gpg = _gpg_binary()
    if not gpg:
        print("gpg not found. Install GPG or set GPG env var.")
        return 2
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("dist/ not found. Run scripts/build_release.py first.")
        return 2
    passphrase = os.environ.get("GPG_PASSPHRASE")
    base_cmd = [gpg, "--batch", "--yes", "--armor", "--detach-sign"]
    if passphrase:
        base_cmd.extend(["--pinentry-mode", "loopback", "--passphrase", passphrase])
    errors = 0
    for artifact in sorted(dist_dir.iterdir()):
        if not artifact.is_file():
            continue
        if artifact.suffix == ".asc":
            continue
        result = subprocess.run(
            [*base_cmd, str(artifact)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors += 1
            sys.stderr.write(result.stderr or "gpg signing failed\n")
    if errors:
        print(f"Signing failed for {errors} artifact(s).")
        return 1
    print(f"Signed artifacts in {dist_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
