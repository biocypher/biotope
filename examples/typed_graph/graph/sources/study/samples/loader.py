"""Project-specific CSV loading; Python's CSV library owns physical parsing."""

import csv
from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, SourceRecord

from .schema import Samples


def load(config: Path) -> Iterator[SourceRecord[Samples]]:
    with config.open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(csv.DictReader(stream), start=2):
            try:
                yield SourceRecord(
                    Samples(
                        sample_id=row["sample_id"],
                        person_id=row["person_id"],
                        tissue=row["tissue"],
                        score=float(row["score"]),
                    ),
                    (Evidence(str(config), "fixture-v1", "samples", f"line:{number}"),),
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(f"{config}:line:{number}: {exc}") from exc
