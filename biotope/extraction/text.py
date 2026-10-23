from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path


CONVERSION = 2
PDF = "application/pdf"
HTML = "text/html"
MEDIA_TYPES = {
    ".pdf": PDF,
    ".html": HTML,
    ".htm": HTML,
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}
IGNORED = re.compile(r"[\s\-\u2010-\u2015\u2212\u00ad\ufffe]")
HIDDEN_TAGS = frozenset({"head", "script", "style", "noscript", "template", "svg", "nav"})
PAGE_TAGS = frozenset({"header", "footer"})
CONTENT_TAGS = frozenset({"main", "article", "section"})
BLOCK_TAGS = frozenset(
    "address article aside blockquote br dd div dl dt figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr "
    "li main nav ol p pre section table tbody tfoot thead tr ul".split()
)


def media_type(path: str) -> str | None:
    return MEDIA_TYPES.get(Path(path).suffix.lower())


def convert(path: Path, kind: str) -> str:
    if kind == PDF:
        return _pdf_text(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    if kind == HTML:
        parser = _TextParser()
        parser.feed(raw)
        parser.close()
        raw = "".join(parser.parts)
    return _tidy(raw)


def _pdf_text(path: Path) -> str:
    import pypdfium2

    document = pypdfium2.PdfDocument(path)
    try:
        pages = [document[index].get_textpage().get_text_range() for index in range(len(document))]
    finally:
        document.close()
    return "\f".join(_tidy(page.replace("\ufffe", "-")) for page in pages)


def _tidy(text: str) -> str:
    lines = (" ".join(line.split()) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    return "\n".join(line for line in lines if line)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0
        self.content = 0
        self.page_parts: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in PAGE_TAGS:
            self.page_parts.append(not self.content)
            self.hidden += not self.content
        if tag in CONTENT_TAGS:
            self.content += 1
        if tag in HIDDEN_TAGS:
            self.hidden += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in PAGE_TAGS and self.page_parts:
            self.hidden = max(0, self.hidden - self.page_parts.pop())
        if tag in CONTENT_TAGS:
            self.content = max(0, self.content - 1)
        if tag in HIDDEN_TAGS:
            self.hidden = max(0, self.hidden - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


class Searchable:
    def __init__(self, text: str) -> None:
        self.text = text
        kept = [(index, char.lower()) for index, char in enumerate(text) if not IGNORED.match(char)]
        self.positions = [index for index, _ in kept]
        self.squeezed = "".join(char for _, char in kept)

    def align(self, quote: str) -> tuple[int, int] | None:
        start = self.text.find(quote)
        if quote.strip() and start >= 0:
            return start, start + len(quote)
        needle = squeeze(quote)
        found = self.squeezed.find(needle) if needle else -1
        if found < 0:
            return None
        return self.positions[found], self.positions[found + len(needle) - 1] + 1

    def count(self, quote: str) -> int:
        needle = squeeze(quote)
        return self.squeezed.count(needle) if needle else 0


def squeeze(text: str) -> str:
    return "".join(char.lower() for char in text if not IGNORED.match(char))


def page(text: str, kind: str, start: int) -> int | None:
    return text.count("\f", 0, start) + 1 if kind == PDF else None
