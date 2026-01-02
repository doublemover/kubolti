"""Fetch tool download URLs from X-Plane developer pages."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; dem2dsf/0.1)"

XPTOOLS_PAGE = "https://developer.x-plane.com/tools/xptools/"
TOOLS_INDEX = "https://developer.x-plane.com/tools/"


class LinkParser(HTMLParser):
    """Collect href attributes from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


@dataclass(frozen=True)
class DownloadCandidate:
    url: str
    platform: str
    version_key: tuple


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - trusted URL
        return response.read().decode("utf-8", "ignore")


def _collect_links(url: str) -> list[str]:
    parser = LinkParser()
    parser.feed(_fetch_html(url))
    return [urljoin(url, link) for link in parser.links]


def _parse_xptools_links(links: Iterable[str]) -> list[DownloadCandidate]:
    candidates: list[DownloadCandidate] = []
    pattern = re.compile(r"xptools_(win|mac|lin)_([\d-]+)\.zip", re.IGNORECASE)
    for link in links:
        match = pattern.search(link)
        if not match:
            continue
        platform = match.group(1).lower()
        version_raw = match.group(2)
        version_key = tuple(int(part) for part in version_raw.split("-") if part.isdigit())
        candidates.append(DownloadCandidate(url=link, platform=platform, version_key=version_key))
    return candidates


def _latest_by_platform(candidates: list[DownloadCandidate]) -> dict[str, str]:
    latest: dict[str, DownloadCandidate] = {}
    for candidate in candidates:
        current = latest.get(candidate.platform)
        if current is None or candidate.version_key > current.version_key:
            latest[candidate.platform] = candidate
    return {platform: entry.url for platform, entry in latest.items()}


def _tools_index_links(links: Iterable[str]) -> list[dict[str, str]]:
    seen = set()
    entries: list[dict[str, str]] = []
    for link in links:
        parsed = urlparse(link)
        if not parsed.netloc.endswith("developer.x-plane.com"):
            continue
        if not parsed.path.startswith("/tools/") or parsed.path == "/tools/":
            continue
        normalized = f"https://{parsed.netloc}{parsed.path}"
        if not normalized.endswith("/"):
            normalized += "/"
        if normalized in seen:
            continue
        seen.add(normalized)
        name = normalized.rstrip("/").split("/")[-1].replace("-", " ")
        entries.append({"name": name, "url": normalized})
    return sorted(entries, key=lambda entry: entry["name"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch tool URLs from X-Plane pages.")
    parser.add_argument(
        "--output",
        help="Optional JSON output path (defaults to stdout).",
    )
    args = parser.parse_args()

    xptools_links = _collect_links(XPTOOLS_PAGE)
    tools_index_links = _collect_links(TOOLS_INDEX)

    xptools_candidates = _parse_xptools_links(xptools_links)

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_pages": {
            "xptools": XPTOOLS_PAGE,
            "tools_index": TOOLS_INDEX,
        },
        "xptools": {
            "latest": _latest_by_platform(xptools_candidates),
            "all": [candidate.url for candidate in xptools_candidates],
        },
        "tools_index": _tools_index_links(tools_index_links),
    }

    output = json.dumps(payload, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
