"""Tests for the bounded static-HTML crawler in biotope/scrape.py."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
import requests

from biotope import scrape
from biotope.scrape import (
    ScrapeError,
    ScrapeResult,
    crawl,
    extract_links,
    normalize_url,
    url_to_relpath,
)


class _Resp:
    """Minimal stand-in for requests.Response."""

    def __init__(
        self,
        text: str,
        status: int = 200,
        content_type: str = "text/html",
        final_url: str | None = None,
    ) -> None:
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        # Mirrors requests.Response.url (the URL after any redirects).
        self.url = final_url or ""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _StubSession:
    """A requests.Session stub serving a fixed URL→response map."""

    def __init__(self, pages: dict[str, _Resp]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def get(self, url: str, **_kwargs) -> _Resp:
        self.requested.append(url)
        value = self.pages.get(url)
        if value is None:
            resp = _Resp("not found", status=404)
        elif isinstance(value, _Resp):
            resp = value
        else:
            resp = _Resp(value)  # bare HTML string → 200 text/html
        # Default the final URL to the requested one (no redirect) unless the
        # fixture explicitly set a redirect target.
        if not resp.url:
            resp.url = url
        return resp


def _html(*hrefs: str) -> str:
    anchors = " ".join(f'<a href="{h}">link</a>' for h in hrefs)
    return f"<html><body>{anchors}</body></html>"


# --------------------------------------------------------------------------- #
# url_to_relpath
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://e.com/", "index.html"),
        ("https://e.com", "index.html"),
        ("https://e.com/topic/", "topic/index.html"),
        ("https://e.com/topic/page", "topic/page.html"),
        ("https://e.com/a/b.html", "a/b.html"),
        ("https://e.com/a/b.htm", "a/b.htm"),
    ],
)
def test_url_to_relpath(url: str, expected: str) -> None:
    assert url_to_relpath(url) == expected


def test_url_to_relpath_disambiguates_query() -> None:
    a = url_to_relpath("https://e.com/list?page=1")
    b = url_to_relpath("https://e.com/list?page=2")
    assert a != b
    assert a.endswith(".html") and b.endswith(".html")


def test_normalize_url_strips_fragment() -> None:
    assert normalize_url("https://e.com/p#section") == "https://e.com/p"


# --------------------------------------------------------------------------- #
# extract_links
# --------------------------------------------------------------------------- #


def test_extract_links_resolves_and_filters() -> None:
    html = _html("/a", "b.html", "#frag", "mailto:x@y.com", "javascript:void(0)", "https://other.com/z")
    links = extract_links(html, "https://e.com/topic/")
    assert "https://e.com/a" in links
    assert "https://e.com/topic/b.html" in links
    assert "https://other.com/z" in links
    # Non-navigational schemes are dropped.
    assert not any(link.startswith(("mailto:", "javascript:")) for link in links)
    assert not any("#frag" in link for link in links)


def test_extract_links_dedupes() -> None:
    html = _html("/a", "/a", "/a#x")
    links = extract_links(html, "https://e.com/")
    assert links.count("https://e.com/a") == 1


# --------------------------------------------------------------------------- #
# crawl
# --------------------------------------------------------------------------- #


def test_crawl_rejects_non_http_seed(tmp_path: Path) -> None:
    with pytest.raises(ScrapeError, match="http"):
        crawl("/local/path", tmp_path, session=_StubSession({}))


def test_crawl_depth_zero_saves_only_seed(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/a"),
        "https://e.com/a": _html(),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    result = crawl("https://e.com/", tmp_path, depth=0, rate=0, session=_StubSession(pages))
    assert [p.url for p in result.pages] == ["https://e.com/"]
    assert (tmp_path / "index.html").exists()


def test_crawl_breadth_first_same_host(tmp_path: Path) -> None:
    pages = {
        "https://e.com/topic/": _html("/topic/a", "b.html", "https://other.com/x"),
        "https://e.com/topic/a": _html("../deep/c"),
        "https://e.com/topic/b.html": _html(),
        "https://e.com/deep/c": _html(),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    session = _StubSession(pages)
    result = crawl("https://e.com/topic/", tmp_path, depth=2, rate=0, session=session)

    saved = {p.url for p in result.pages}
    assert saved == {
        "https://e.com/topic/",
        "https://e.com/topic/a",
        "https://e.com/topic/b.html",
        "https://e.com/deep/c",
    }
    # Cross-host link is never fetched.
    assert "https://other.com/x" not in session.requested
    assert result.host == "e.com"


def test_crawl_respects_robots(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/secret", "/ok"),
        "https://e.com/ok": _html(),
        "https://e.com/secret": _html(),
        "https://e.com/robots.txt": _Resp("User-agent: *\nDisallow: /secret\n", content_type="text/plain"),
    }
    session = _StubSession(pages)
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, session=session)

    saved = {p.url for p in result.pages}
    assert "https://e.com/ok" in saved
    assert "https://e.com/secret" not in saved
    assert "https://e.com/secret" not in session.requested
    assert any("robots" in reason for _url, reason in result.skipped)


def test_crawl_ignore_robots(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/secret"),
        "https://e.com/secret": _html(),
        "https://e.com/robots.txt": _Resp("User-agent: *\nDisallow: /secret\n", content_type="text/plain"),
    }
    session = _StubSession(pages)
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, respect_robots=False, session=session)
    assert "https://e.com/secret" in {p.url for p in result.pages}
    # robots.txt is not even fetched when ignored.
    assert "https://e.com/robots.txt" not in session.requested


def test_crawl_skips_non_html(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/data.csv"),
        "https://e.com/data.csv": _Resp("a,b\n1,2", content_type="text/csv"),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, session=_StubSession(pages))
    assert [p.url for p in result.pages] == ["https://e.com/"]
    assert any("non-HTML" in reason for _url, reason in result.skipped)


def test_crawl_honours_max_pages(tmp_path: Path) -> None:
    pages = {"https://e.com/robots.txt": _Resp("", status=404)}
    # A fan of 10 same-host links from the seed.
    seed_links = [f"/p{i}" for i in range(10)]
    pages["https://e.com/"] = _html(*seed_links)
    for i in range(10):
        pages[f"https://e.com/p{i}"] = _html()
    result = crawl("https://e.com/", tmp_path, depth=1, max_pages=3, rate=0, session=_StubSession(pages))
    assert len(result.pages) == 3


def test_crawl_skips_failed_fetch(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/missing"),
        "https://e.com/missing": _Resp("nope", status=500),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, session=_StubSession(pages))
    assert [p.url for p in result.pages] == ["https://e.com/"]
    assert any("fetch error" in reason for _url, reason in result.skipped)


def test_crawl_rate_limit_sleeps(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/a"),
        "https://e.com/a": _html(),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    with mock.patch.object(scrape.time, "sleep") as sleep:
        crawl("https://e.com/", tmp_path, depth=1, rate=5.0, session=_StubSession(pages))
    # With >1 page and a positive rate, at least one throttle sleep happens.
    assert sleep.called


def test_crawl_path_traversal_is_contained(tmp_path: Path) -> None:
    # A server linking to encoded traversal must not escape the dest dir.
    pages = {
        "https://e.com/": _html("/../../etc/passwd"),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    crawl("https://e.com/", tmp_path, depth=1, rate=0, session=_StubSession(pages))
    # Nothing was written outside tmp_path.
    escaped = tmp_path.parent / "etc" / "passwd"
    assert not escaped.exists()


def test_scrape_result_defaults() -> None:
    result = ScrapeResult(host="e.com")
    assert result.pages == []
    assert result.skipped == []


def test_crawl_dedupes_urls_collapsing_to_same_relpath(tmp_path: Path) -> None:
    # /about and /about.html both map to about.html — only one should be saved.
    pages = {
        "https://e.com/": _html("/about", "/about.html"),
        "https://e.com/about": _html(),
        "https://e.com/about.html": _html(),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, session=_StubSession(pages))
    relpaths = [str(p.relpath) for p in result.pages]
    assert relpaths.count("about.html") == 1
    assert any(reason == "duplicate path" for _url, reason in result.skipped)


def test_crawl_honours_robots_crawl_delay(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/a"),
        "https://e.com/a": _html(),
        "https://e.com/robots.txt": _Resp("User-agent: *\nCrawl-delay: 5\n", content_type="text/plain"),
    }
    with mock.patch.object(scrape.time, "sleep") as sleep:
        # Even with a fast --rate, the 5s crawl-delay should dominate the pace.
        crawl("https://e.com/", tmp_path, depth=1, rate=1000.0, session=_StubSession(pages))
    assert any(call.args and call.args[0] >= 4.5 for call in sleep.call_args_list)


def test_crawl_skips_offhost_redirect(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/jump"),
        # /jump redirects off-host; requests would expose this via response.url.
        "https://e.com/jump": _Resp(_html(), final_url="https://evil.com/landing"),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, session=_StubSession(pages))
    saved = {p.url for p in result.pages}
    assert "https://evil.com/landing" not in saved
    assert not (tmp_path / "landing.html").exists()
    assert any("off-host" in reason for _url, reason in result.skipped)


def test_crawl_follows_samehost_redirect_and_records_final_url(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/old"),
        "https://e.com/old": _Resp(_html(), final_url="https://e.com/new"),
        "https://e.com/robots.txt": _Resp("", status=404),
    }
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, session=_StubSession(pages))
    saved = {p.url for p in result.pages}
    # The page is saved under its final URL, not the requested one.
    assert "https://e.com/new" in saved
    assert (tmp_path / "new.html").exists()


def test_crawl_5xx_robots_disallows_all(tmp_path: Path) -> None:
    pages = {
        "https://e.com/": _html("/a"),
        "https://e.com/a": _html(),
        "https://e.com/robots.txt": _Resp("oops", status=503),
    }
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, session=_StubSession(pages))
    assert result.pages == []
    assert any("robots" in reason for _url, reason in result.skipped)


def test_crawl_robots_network_failure_allows_all(tmp_path: Path) -> None:
    class _RobotsBoom(_StubSession):
        def get(self, url: str, **kwargs):
            if url.endswith("/robots.txt"):
                raise requests.ConnectionError("boom")
            return super().get(url, **kwargs)

    pages = {
        "https://e.com/": _html("/a"),
        "https://e.com/a": _html(),
    }
    result = crawl("https://e.com/", tmp_path, depth=1, rate=0, session=_RobotsBoom(pages))
    # A transient robots fetch failure must not block the user-requested crawl.
    assert {p.url for p in result.pages} == {"https://e.com/", "https://e.com/a"}
