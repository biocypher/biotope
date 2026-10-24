import csv
from collections.abc import Iterator

from biotope.graph import Evidence, RunContext, SourceRecord

from ...paths import PROJECT_ROOT
from . import SOURCE
from .schema import Push


PATH = PROJECT_ROOT / "raw/push.csv"


def _read(config: None) -> Iterator[SourceRecord[Push]]:
    with PATH.open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(csv.DictReader(stream), start=2):
            yield SourceRecord(
                Push(
                    doi=row["doi"],
                    title=row["title"],
                    orcid=row["orcid"],
                    position=int(row["position"]) if row["position"] else None,
                ),
                (Evidence("raw/push.csv", "fixture-v1", "push", f"line:{number}"),),
            )


def load(context: RunContext) -> Iterator[SourceRecord[Push]]:
    yield from context.load(SOURCE, _read, None)
