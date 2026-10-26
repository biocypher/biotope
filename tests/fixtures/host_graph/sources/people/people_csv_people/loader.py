from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, RunContext, SourceRecord

from . import SOURCE
from .schema import PeopleCsvPeople


def _read(path: Path) -> Iterator[SourceRecord[PeopleCsvPeople]]:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines()[1:], start=1):
        person_id, name = line.split(",")
        evidence = Evidence(path.as_posix(), "v1", PeopleCsvPeople.__record_set__, f"row {number}")
        yield SourceRecord(PeopleCsvPeople(person_id=person_id, name=name), (evidence,))


def load(context: RunContext) -> Iterator[SourceRecord[PeopleCsvPeople]]:
    yield from context.load(SOURCE, _read, SOURCE.path())
