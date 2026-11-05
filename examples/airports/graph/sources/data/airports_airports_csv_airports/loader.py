"""Decode the airport table into its schema, one record per row."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, RunContext, SourceRecord

from .._files import cited
from . import SOURCE
from .schema import AirportRow


def _read(path: Path) -> Iterator[SourceRecord[AirportRow]]:
    """Yield one record per row of airports.csv, preserving every described field; nothing is filtered."""
    artifact, version = cited(path)
    with path.open(newline="", encoding="utf-8") as stream:
        for line, row in enumerate(csv.DictReader(stream), start=2):
            yield SourceRecord(
                AirportRow(
                    airport_iata=row["iata"],
                    name=row["name"],
                    city=row["city"],
                    country=row["country"],
                ),
                (Evidence(artifact, version, AirportRow.__record_set__, f"line {line}"),),
            )


def load(context: RunContext) -> Iterator[SourceRecord[AirportRow]]:
    yield from context.load(SOURCE, _read, SOURCE.path())
