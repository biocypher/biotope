from __future__ import annotations

import mimetypes
import re
from html.parser import HTMLParser
from pathlib import Path


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
HIDDEN_TAGS = frozenset({"head", "script", "style", "noscript", "template", "svg"})
BLOCK_TAGS = frozenset(
    "address article aside blockquote br dd div dl dt figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr "
    "li main nav ol p pre section table tbody tfoot thead tr ul".split()
)


def media_type(path: str, declared: object = None) -> str | None:
    suffix = Path(path).suffix.lower()
    if suffix in MEDIA_TYPES:
        return MEDIA_TYPES[suffix]
    if isinstance(declared, str) and declared in MEDIA_TYPES.values():
        return declared
    guessed = mimetypes.guess_type(path)[0]
    return guessed if guessed in MEDIA_TYPES.values() else None


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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in HIDDEN_TAGS:
            self.hidden += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in HIDDEN_TAGS:
            self.hidden = max(0, self.hidden - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def align(text: str, quote: str) -> tuple[int, int] | None:
    start = text.find(quote)
    if quote.strip() and start >= 0:
        return start, start + len(quote)
    kept = [(index, char.lower()) for index, char in enumerate(text) if not IGNORED.match(char)]
    needle = "".join(char.lower() for char in quote if not IGNORED.match(char))
    found = "".join(char for _, char in kept).find(needle) if needle else -1
    if found < 0:
        return None
    return kept[found][0], kept[found + len(needle) - 1][0] + 1


def page(text: str, kind: str, start: int) -> int | None:
    return text.count("\f", 0, start) + 1 if kind == PDF else None
