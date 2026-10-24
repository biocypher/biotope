import csv
from collections.abc import Iterator

from biotope.graph import Evidence, RunContext, SourceRecord

from ....paths import PROJECT_ROOT
from . import SOURCE
from .schema import StudyB


PATH = PROJECT_ROOT / "raw/study_b.csv"


def _read(config: None) -> Iterator[SourceRecord[StudyB]]:
    with PATH.open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(csv.DictReader(stream), start=2):
            yield SourceRecord(
                StudyB(row=int(row["row"]), ensembl=row["ensembl"] or None, symbol=row["symbol"]),
                (Evidence("raw/study_b.csv", "fixture-v1", "study_b", f"line:{number}"),),
            )


def load(context: RunContext) -> Iterator[SourceRecord[StudyB]]:
    yield from context.load(SOURCE, _read, None)
