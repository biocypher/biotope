"""Bounded, polite static-HTML crawler backing ``biotope get --crawl``.

v1 scope (issue #22): static HTML only, same-host breadth-first crawl to a
bounded depth with a page cap, ``robots.txt`` respected by default, and a
request rate limit. JS rendering, cross-host crawls, authentication, and
non-HTML transports are deliberately out of scope.

The module is intentionally free of any biotope-manifest knowledge: it fetches
and saves pages, then returns what it saved so the caller can bake a manifest.
"""

from __future__ import annotations

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests


DEFAULT_USER_AGENT = "biotope-get/1.0 (+https://github.com/biocypher/biotope)"
HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_NON_HTTP_LINK_PREFIXES = ("#", "mailto:", "javascript:", "tel:", "data:", "ftp:")


class ScrapeError(RuntimeError):
    """Raised when a crawl cannot proceed (bad seed, missing dependency, …)."""


@dataclass(frozen=True)
class ScrapedPage:
    """One saved page: its source URL and the file path relative to the dest dir."""

    url: str
    relpath: Path


@dataclass
class ScrapeResult:
    """Outcome of a crawl: what was saved, what was skipped, and the host."""

    host: str
    pages: list[ScrapedPage] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def normalize_url(url: str) -> str:
    """Drop the fragment from a URL; everything else is preserved verbatim."""
    return urldefrag(url)[0]


def url_to_relpath(url: str) -> str:
    """Derive a filesystem-safe, ``.html``-suffixed relative path from a URL.

    The host is *not* encoded here — the caller roots the crawl at a per-host
    directory. Directory-style URLs map to ``index.html``; query strings are
    disambiguated with a short digest so ``?page=1`` and ``?page=2`` don't
    collide.
    """
    parsed = urlparse(url)
    path = parsed.path or "/"

    if path in ("", "/"):
        rel = "index.html"
    else:
        rel = path.lstrip("/")
        if path.endswith("/"):
            rel = f"{rel}index.html"
        elif PurePosixPath(rel).suffix.lower() not in (".html", ".htm"):
            rel = f"{rel}.html"

    if parsed.query:
        digest = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]  # noqa: S324 - non-crypto disambiguator
        p = PurePosixPath(rel)
        rel = str(p.with_name(f"{p.stem}__{digest}{p.suffix}"))

    return rel


def _safe_join(dest_dir: Path, relpath: str) -> Path | None:
    """Resolve ``relpath`` under ``dest_dir``, rejecting any escape (``..``)."""
    dest_resolved = dest_dir.resolve()
    candidate = (dest_resolved / relpath).resolve()
    try:
        candidate.relative_to(dest_resolved)
    except ValueError:
        return None
    return candidate


def _require_beautifulsoup():
    """Import BeautifulSoup lazily with a friendly error if it's missing."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        msg = "beautifulsoup4 is required for `biotope get --crawl`. Install it with `uv pip install beautifulsoup4`."
        raise ScrapeError(msg) from exc
    return BeautifulSoup


def extract_links(html: str, base_url: str) -> list[str]:
    """Return absolute, fragment-stripped ``http(s)`` links found in ``html``."""
    beautiful_soup = _require_beautifulsoup()
    soup = beautiful_soup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.lower().startswith(_NON_HTTP_LINK_PREFIXES):
            continue
        absolute = normalize_url(urljoin(base_url, href))
        if urlparse(absolute).scheme not in ("http", "https"):
            continue
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)
    return links


def _load_robots(
    seed_url: str,
    session: requests.Session,
    user_agent: str,
    timeout: int,
) -> RobotFileParser:
    """Fetch and parse ``robots.txt`` for the seed's host.

    Status handling follows common crawler convention:

    * ``2xx`` — use the published rules.
    * ``4xx`` (e.g. 404) — no policy exists, so allow all.
    * ``5xx`` — the server is erroring; be conservative and treat as
      disallow-all for this run rather than risk crawling against intent.
    * network failure — the user explicitly chose to crawl this host and
      ``robots.txt`` is simply unreachable, so fall back to allow-all.
    """
    parsed = urlparse(seed_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    try:
        response = session.get(robots_url, timeout=timeout, headers={"User-Agent": user_agent})
    except requests.RequestException:
        parser.parse([])
        return parser
    if response.status_code >= 500:
        parser.parse(["User-agent: *", "Disallow: /"])
    elif response.status_code >= 400:
        parser.parse([])
    else:
        parser.parse(response.text.splitlines())
    return parser


def _content_type(response: requests.Response) -> str:
    """Return the lower-cased MIME type (without parameters) of a response."""
    return response.headers.get("Content-Type", "").split(";")[0].strip().lower()


def crawl(
    seed_url: str,
    dest_dir: Path,
    *,
    depth: int = 1,
    max_pages: int = 50,
    rate: float = 1.0,
    respect_robots: bool = True,
    session: requests.Session | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = 30,
    echo: Callable[[str], None] | None = None,
) -> ScrapeResult:
    """Crawl ``seed_url`` breadth-first, saving same-host HTML pages under ``dest_dir``.

    Args:
        seed_url: The ``http(s)`` page to start from.
        dest_dir: Directory (created as needed) that saved pages are rooted at.
        depth: Number of link-following hops from the seed (0 = seed only).
        max_pages: Hard cap on pages saved (the per-host link cap for v1).
        rate: Requests per second; consecutive fetches are throttled to ``1/rate``.
        respect_robots: Honour the host's ``robots.txt`` (default True).
        session: Optional pre-built requests session (injectable for tests).
        user_agent: User-Agent sent on every request and matched against robots.
        timeout: Per-request timeout in seconds.
        echo: Optional progress sink (e.g. ``click.echo``); keeps this module
            free of any CLI dependency.

    Returns:
        A :class:`ScrapeResult` listing saved pages and skipped URLs.

    Raises:
        ScrapeError: If the seed is not an ``http(s)`` URL.
    """
    parsed_seed = urlparse(seed_url)
    if parsed_seed.scheme not in ("http", "https") or not parsed_seed.netloc:
        msg = f"--crawl needs an http(s) URL; got {seed_url!r}"
        raise ScrapeError(msg)

    note = echo or (lambda _message: None)
    session = session or requests.Session()
    host = parsed_seed.netloc
    interval = 1.0 / rate if rate and rate > 0 else 0.0

    robots = _load_robots(seed_url, session, user_agent, timeout) if respect_robots else None
    if robots is not None:
        # Honour a host-requested Crawl-delay if it asks for a slower pace than --rate.
        crawl_delay = robots.crawl_delay(user_agent)
        if crawl_delay:
            interval = max(interval, float(crawl_delay))

    result = ScrapeResult(host=host)
    visited: set[str] = set()
    seen_relpaths: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(normalize_url(seed_url), 0)])
    last_fetch = 0.0

    while queue and len(result.pages) < max_pages:
        url, current_depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if urlparse(url).netloc != host:
            result.skipped.append((url, "different host"))
            continue
        if robots is not None and not robots.can_fetch(user_agent, url):
            result.skipped.append((url, "blocked by robots.txt"))
            note(f"  ⏭️  robots.txt disallows {url}")
            continue

        if interval:
            wait = last_fetch + interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        last_fetch = time.monotonic()

        try:
            response = session.get(url, timeout=timeout, headers={"User-Agent": user_agent})
            response.raise_for_status()
        except requests.RequestException as exc:
            result.skipped.append((url, f"fetch error: {exc}"))
            note(f"  ⚠️  could not fetch {url}: {exc}")
            continue

        # Follow where redirects actually landed. A same-host URL that redirects
        # off-host must not be saved under the seed host (it would break the
        # same-host guarantee and mis-attribute provenance).
        final_url = normalize_url(str(response.url))
        if urlparse(final_url).netloc != host:
            result.skipped.append((url, f"redirected off-host → {urlparse(final_url).netloc}"))
            continue
        visited.add(final_url)

        content_type = _content_type(response)
        if content_type and content_type not in HTML_CONTENT_TYPES:
            result.skipped.append((final_url, f"non-HTML ({content_type})"))
            continue

        relpath = url_to_relpath(final_url)
        if relpath in seen_relpaths:
            # Two distinct URLs collapsed to the same file (e.g. /a and /a.html).
            result.skipped.append((final_url, "duplicate path"))
            continue
        out_path = _safe_join(dest_dir, relpath)
        if out_path is None:
            result.skipped.append((final_url, "unsafe path"))
            continue
        seen_relpaths.add(relpath)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(response.content)
        result.pages.append(ScrapedPage(url=final_url, relpath=out_path.relative_to(dest_dir.resolve())))
        note(f"  📄 {final_url} → {out_path.relative_to(dest_dir.resolve())}")

        if current_depth < depth:
            try:
                links = extract_links(response.text, final_url)
            except ScrapeError:
                raise
            except Exception as exc:  # noqa: BLE001 - a single bad page shouldn't abort the crawl
                note(f"  ⚠️  could not parse links from {final_url}: {exc}")
                links = []
            for link in links:
                if urlparse(link).netloc == host and link not in visited:
                    queue.append((link, current_depth + 1))

    return result
