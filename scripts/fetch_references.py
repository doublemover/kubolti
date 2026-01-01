"""Fetch and extract reference text from URLs."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None

def collect_urls(spec_path: Path) -> list[str]:
    """Collect reference URLs from a spec or URL list."""
    text = spec_path.read_text(encoding="utf-8")
    urls = re.findall(r"`(https?://[^`]+)`", text)
    if not urls:
        urls = re.findall(r"https?://\\S+", text)
    cleaned = []
    for url in urls:
        url = url.strip().rstrip(").,")
        cleaned.append(url)
    seen = set()
    ordered = []
    for url in cleaned:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def slugify(url: str) -> str:
    """Convert a URL into a safe filename slug."""
    parsed = urlparse(url)
    base = (parsed.netloc + parsed.path).strip("/")
    base = base.replace("/", "_")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    base = base.strip("_")
    return base or "reference"


BLOCK_PHRASES = (
    "verifying you are human",
    "enable javascript and cookies to continue",
    "checking your browser before accessing",
    "access denied",
    "cloudflare",
)


def looks_blocked(text: str) -> bool:
    """Heuristic check for bot-blocked pages."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in BLOCK_PHRASES)


def extract_text_bs4(html: str) -> str | None:
    """Extract text content using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    root = soup.body or soup
    text = root.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip() or None


def extract_text(html: str | None) -> str | None:
    """Extract readable text from raw HTML."""
    if not html:
        return None
    text = trafilatura.extract(html, include_comments=False, include_links=False)
    if not text:
        text = extract_text_bs4(html)
    if not text:
        return None
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if text and looks_blocked(text):
        return None
    return text or None


def fetch_with_httpx(client: httpx.Client, url: str) -> str | None:
    """Fetch a URL via httpx."""
    resp = client.get(url)
    resp.raise_for_status()
    return resp.text


def fetch_with_playwright(url: str, timeout_ms: int) -> str | None:
    """Fetch a URL using Playwright rendering."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
        if stealth_sync:
            stealth_sync(page)
        page.set_default_timeout(timeout_ms)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)
        html = page.content()
        browser.close()
        return html


def main() -> int:
    """CLI entrypoint for fetching reference sources."""
    parser = argparse.ArgumentParser(description="Fetch reference sources.")
    parser.add_argument(
        "--spec",
        default="dem2dsf_xp12_spec_v0_2.md",
        help="Path to the spec file containing reference URLs.",
    )
    parser.add_argument(
        "--urls-file",
        default=None,
        help="Optional file containing URLs (one per line) to fetch.",
    )
    parser.add_argument(
        "--urls",
        nargs="*",
        default=None,
        help="Optional list of URLs to fetch.",
    )
    parser.add_argument(
        "--out-dir",
        default="docs/references/_raw",
        help="Directory for extracted text files.",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Optional JSON report output path.",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=200,
        help="Minimum extracted text length to treat as success.",
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=20.0,
        help="Timeout in seconds for HTTP fetches.",
    )
    parser.add_argument(
        "--playwright-timeout",
        type=int,
        default=20000,
        help="Timeout in milliseconds for Playwright fetches.",
    )
    parser.add_argument(
        "--no-playwright",
        action="store_true",
        help="Skip Playwright fallback.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = Path(args.report) if args.report else out_dir / "fetch_report.json"
    urls = []
    if args.urls_file:
        urls_file = Path(args.urls_file)
        if urls_file.exists():
            url_lines = urls_file.read_text(encoding="utf-8").splitlines()
            urls.extend([line.strip() for line in url_lines])
    if args.urls:
        urls.extend(args.urls)
    if not urls:
        spec_path = Path(args.spec)
        urls = collect_urls(spec_path)
    urls = [u for u in urls if u]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    results = {}

    with httpx.Client(follow_redirects=True, headers=headers, timeout=args.http_timeout) as client:
        for url in urls:
            slug = slugify(url)
            out_path = out_dir / f"{slug}.txt"
            result = {"url": url, "status": "failed", "method": None, "path": None}
            try:
                html = fetch_with_httpx(client, url)
                text = extract_text(html)
                if not text or len(text) < args.min_chars:
                    raise ValueError("insufficient text from httpx")
                out_path.write_text(
                    text.encode("ascii", "ignore").decode("ascii"), encoding="ascii"
                )
                result.update(
                    {"status": "ok", "method": "httpx", "path": str(out_path)}
                )
            except Exception as exc:
                if args.no_playwright:
                    result["error"] = f"{type(exc).__name__}: {exc}"
                else:
                    try:
                        html = fetch_with_playwright(url, timeout_ms=args.playwright_timeout)
                        text = extract_text(html)
                        if not text or len(text) < args.min_chars:
                            raise ValueError("insufficient text from playwright")
                        out_path.write_text(
                            text.encode("ascii", "ignore").decode("ascii"),
                            encoding="ascii",
                        )
                        result.update(
                            {
                                "status": "ok",
                                "method": "playwright",
                                "path": str(out_path),
                            }
                        )
                    except (PlaywrightTimeoutError, Exception) as exc2:
                        result["error"] = f"{type(exc2).__name__}: {exc2}"
            results[slug] = result

    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
