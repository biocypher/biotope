# biotope:placeholder
"""Copy this module for one kind of document: the schema of its records and the extractor that reads it."""

from dataclasses import dataclass, field
from typing import Any

from biotope.extraction import Document, Extractor, Schema


@dataclass(frozen=True, kw_only=True)
class Record:
    """Say what the document is and which records to extract from it."""

    value: str = field(metadata={"description": "Say exactly what to fill."})


class RecordExtractor(Extractor):
    name = "record-extractor"
    version = "1"

    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]:
        raise NotImplementedError("Read document.path and return each record's values with a quote or a locator")
