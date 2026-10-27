import csv
from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, RunContext, SourceRecord

from . import SOURCE
from .schema import PushPeopleCsvPeople


def _read(path: Path) -> Iterator[SourceRecord[PushPeopleCsvPeople]]:
    with path.open(newline="", encoding="utf-8") as stream:
        for line, row in enumerate(csv.DictReader(stream), start=2):
            record = PushPeopleCsvPeople(person_id=row["person_id"], name=row["name"])
            evidence = Evidence(path.as_posix(), "v1", PushPeopleCsvPeople.__record_set__, f"line {line}")
            yield SourceRecord(record, (evidence,))


def load(context: RunContext) -> Iterator[SourceRecord[PushPeopleCsvPeople]]:
    yield from context.load(SOURCE, _read, SOURCE.path())
