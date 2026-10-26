from collections.abc import Iterator

from biotope.graph import Evidence, RunContext, SourceRecord

from ....paths import PROJECT_ROOT
from . import SOURCE
from .schema import People


PATH = PROJECT_ROOT / "data/raw/people/people.csv"


def _read(config: None) -> Iterator[SourceRecord[People]]:
    for number, line in enumerate(PATH.read_text(encoding="utf-8").splitlines()[1:], start=1):
        person_id, name = line.split(",")
        yield SourceRecord(
            People(person_id=person_id, name=name), (Evidence(str(PATH), "v1", "people", f"row {number}"),)
        )


def load(context: RunContext) -> Iterator[SourceRecord[People]]:
    yield from context.load(SOURCE, _read, None)
