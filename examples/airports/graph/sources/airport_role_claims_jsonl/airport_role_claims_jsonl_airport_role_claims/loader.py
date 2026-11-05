"""Decode the stored extraction of the notes, one record per line, each citing the notes."""

import json
from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, RunContext, SourceRecord

from . import SOURCE
from .schema import StoredRoleClaim


def _read(path: Path) -> Iterator[SourceRecord[StoredRoleClaim]]:
    """Yield one record per stored line; its evidence is the notes document, its digest and the claim's line."""
    with path.open(encoding="utf-8") as stream:
        for text in stream:
            stored = json.loads(text)
            values = {name: entry["value"] for name, entry in stored["values"].items()}
            evidence = Evidence(
                stored["document"],
                "sha256:" + stored["provenance"]["document_sha256"],
                StoredRoleClaim.__record_set__,
                stored["values"]["role"]["evidence"]["locator"],
            )
            yield SourceRecord(StoredRoleClaim(id=stored["id"], document=stored["document"], **values), (evidence,))


def load(context: RunContext) -> Iterator[SourceRecord[StoredRoleClaim]]:
    yield from context.load(SOURCE, _read, SOURCE.path())
