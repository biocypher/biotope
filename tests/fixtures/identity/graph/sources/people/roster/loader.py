import csv
from collections.abc import Iterator

from biotope.graph import Evidence, RunContext, SourceRecord

from ....paths import PROJECT_ROOT
from . import SOURCE
from .schema import Roster


PATH = PROJECT_ROOT / "raw/roster.csv"


def _read(config: None) -> Iterator[SourceRecord[Roster]]:
    with PATH.open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(csv.DictReader(stream), start=2):
            yield SourceRecord(
                Roster(record=row["record"], name=row["name"], email=row["email"] or None, orcid=row["orcid"] or None),
                (Evidence("raw/roster.csv", "fixture-v1", "roster", f"line:{number}"),),
            )


def load(context: RunContext) -> Iterator[SourceRecord[Roster]]:
    yield from context.load(SOURCE, _read, None)
