"""Decode the airline table into its schema, one record per row."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, RunContext, SourceRecord

from .._files import cited
from . import SOURCE
from .schema import AirlineRow


def _read(path: Path) -> Iterator[SourceRecord[AirlineRow]]:
    """Yield one record per row of airlines.csv, preserving every described field; nothing is filtered."""
    artifact, version = cited(path)
    with path.open(newline="", encoding="utf-8") as stream:
        for line, row in enumerate(csv.DictReader(stream), start=2):
            yield SourceRecord(
                AirlineRow(
                    airline_code=row["code"],
                    airline_name=row["name"],
                ),
                (Evidence(artifact, version, AirlineRow.__record_set__, f"line {line}"),),
            )


def load(context: RunContext) -> Iterator[SourceRecord[AirlineRow]]:
    yield from context.load(SOURCE, _read, SOURCE.path())
