"""Build XPTools from the pinned X-Plane/xptools tag."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from dem2dsf.tools.installer import ensure_tool_config
from dem2dsf.tools.xptools_build import (
    XPTOOLS_COMMIT,
    XPTOOLS_REPO_URL,
    XPTOOLS_TAG,
    build_xptools,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build X-Plane/xptools utilities.")
    parser.add_argument(
        "--root",
        help="Root directory for source and installed tools (default: <repo>/tools).",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Attempt to install build dependencies.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable prompts when installing dependencies.",
    )
    parser.add_argument(
        "--skip-xptools",
        action="store_true",
        help="Skip building DSFTool/DDSTool.",
    )
    parser.add_argument(
        "--xptools-tag",
        default=XPTOOLS_TAG,
        help=f"Git tag for DSFTool/DDSTool (default: {XPTOOLS_TAG}).",
    )
    parser.add_argument(
        "--xptools-commit",
        default=XPTOOLS_COMMIT,
        help="Optional pinned commit SHA for the xptools tag (omit to use tag only).",
    )
    parser.add_argument(
        "--repo-url",
        default=XPTOOLS_REPO_URL,
        help="X-Plane/xptools repo URL.",
    )
    parser.add_argument(
        "--write-config",
        action="store_true",
        help="Write tools/tool_paths.json with built tool paths.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    tools_root = Path(args.root) if args.root else repo_root / "tools"

    install_deps = args.install_deps
    interactive = not args.non_interactive

    built_paths: dict[str, Path] = {}

    def find_existing(names: tuple[str, ...], root: Path) -> Path | None:
        for name in names:
            found = shutil.which(name)
            if found:
                return Path(found)
        if root.exists():
            for name in names:
                for candidate in root.rglob(name):
                    if candidate.is_file():
                        return candidate
        return None

    if not args.skip_xptools:
        install_dir = tools_root / "xptools"
        existing_dsftool = find_existing(("DSFTool.exe", "DSFTool", "dsftool"), install_dir)
        existing_ddstool = find_existing(("DDSTool.exe", "DDSTool", "ddstool"), install_dir)
        if existing_dsftool and existing_ddstool:
            built_paths["dsftool"] = existing_dsftool
            built_paths["ddstool"] = existing_ddstool
            print(f"Using existing DSFTool/DDSTool at {install_dir}")
        else:
            tools = build_xptools(
                source_dir=tools_root / "xptools-src",
                install_dir=install_dir,
                repo_url=args.repo_url,
                tag=args.xptools_tag,
                commit=args.xptools_commit,
                install_deps=install_deps,
                interactive=interactive,
            )
            for tool in tools:
                built_paths[tool.name] = tool.path
            print(f"Built DSFTool/DDSTool at {tools_root / 'xptools'}")

    if args.write_config and built_paths:
        config_path = ensure_tool_config(tools_root / "tool_paths.json", built_paths)
        print(f"Wrote tool config to {config_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
