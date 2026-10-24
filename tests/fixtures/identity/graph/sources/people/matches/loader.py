import csv
from collections.abc import Iterator

from biotope.graph import Evidence, RunContext, SourceRecord

from ....paths import PROJECT_ROOT
from . import SOURCE
from .schema import Matches


PATH = PROJECT_ROOT / "raw/matches.sssom.tsv"


def _read(config: None) -> Iterator[SourceRecord[Matches]]:
    with PATH.open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(
            csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t"), start=2
        ):
            yield SourceRecord(
                Matches(
                    subject_id=row["subject_id"],
                    predicate_id=row["predicate_id"],
                    object_id=row["object_id"],
                    mapping_justification=row["mapping_justification"],
                    confidence=float(row["confidence"]) if row["confidence"] else None,
                ),
                (Evidence("raw/matches.sssom.tsv", "fixture-v1", "matches", f"row:{number}"),),
            )


def load(context: RunContext) -> Iterator[SourceRecord[Matches]]:
    yield from context.load(SOURCE, _read, None)
