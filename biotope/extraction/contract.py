from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol


if TYPE_CHECKING:
    from biotope.extraction.schema import Schema


@dataclass(frozen=True)
class Document:
    path: str
    sha256: str
    media_type: str
    text: str


class ExtractionError(Exception):
    pass


class Extractor(Protocol):
    name: str
    version: str
    settings: Mapping[str, object]

    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]: ...
