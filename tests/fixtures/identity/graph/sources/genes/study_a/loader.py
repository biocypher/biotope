import csv
from collections.abc import Iterator

from biotope.graph import Evidence, RunContext, SourceRecord

from ....paths import PROJECT_ROOT
from . import SOURCE
from .schema import StudyA


PATH = PROJECT_ROOT / "raw/study_a.csv"


def _read(config: None) -> Iterator[SourceRecord[StudyA]]:
    with PATH.open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(csv.DictReader(stream), start=2):
            yield SourceRecord(
                StudyA(row=int(row["row"]), ensembl=row["ensembl"] or None, symbol=row["symbol"]),
                (Evidence("raw/study_a.csv", "fixture-v1", "study_a", f"line:{number}"),),
            )


def load(context: RunContext) -> Iterator[SourceRecord[StudyA]]:
    yield from context.load(SOURCE, _read, None)
