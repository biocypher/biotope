import csv
from collections.abc import Iterator

from biotope.graph import Evidence, RunContext, SourceRecord

from ...paths import PROJECT_ROOT
from . import SOURCE
from .schema import Directory


PATH = PROJECT_ROOT / "raw/directory.csv"


def _read(config: None) -> Iterator[SourceRecord[Directory]]:
    with PATH.open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(csv.DictReader(stream), start=2):
            yield SourceRecord(
                Directory(upn=row["upn"], name=row["name"], roster=row["roster"] or None),
                (Evidence("raw/directory.csv", "fixture-v1", "directory", f"line:{number}"),),
            )


def load(context: RunContext) -> Iterator[SourceRecord[Directory]]:
    yield from context.load(SOURCE, _read, None)
