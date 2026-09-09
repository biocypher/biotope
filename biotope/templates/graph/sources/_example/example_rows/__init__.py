"""Illustrative registration; intentionally absent from the active SOURCES."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import RECORDS


SOURCE = SourceContract(
    name="_example/example_rows",
    metadata=Path(__file__).resolve().parent / "../metadata.jsonld",
    generated=Path(__file__).with_name("schema.py"),
    records=RECORDS,
)
