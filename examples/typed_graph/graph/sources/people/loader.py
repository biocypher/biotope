"""Project-specific people input; no joins or scientific filters in the loader."""

import csv
from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, SourceRecord

from .schema import People


def load(config: Path) -> Iterator[SourceRecord[People]]:
    with config.open(newline="", encoding="utf-8") as stream:
        for number, row in enumerate(csv.DictReader(stream), start=2):
            try:
                yield SourceRecord(
                    People(person_id=row["person_id"], name=row["name"]),
                    (Evidence(str(config), "fixture-v1", "people", f"line:{number}"),),
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(f"{config}:line:{number}: {exc}") from exc
