"""Illustrative typed transformations; replace identities and policies before use.

Shown as two steps — normalize, then build graph objects — because that is the form
worth seeing written down. A source row that maps cleanly onto its concepts needs no
intermediate: annotate ``map_record`` with ``SourceRecord[ExampleRows]`` and delete
``normalise_record``. Add the split when sources must converge on one shape, when a
stage needs buffering or aggregation, or when one normalization feeds several mappings.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from biotope.graph import Mapping, SourceRecord

from ..sources._example.example_rows.schema import ExampleRows
from ..topology._example_collection.node import Collection, CollectionId
from ..topology._example_record.in_collection import InCollection
from ..topology._example_record.node import Record, RecordId


@dataclass(frozen=True)
class ExampleValue:
    """An intermediate: source decisions resolved, graph identity not yet minted."""

    record_id: str
    collection_id: str
    value: float | None


def normalise_record(row: SourceRecord[ExampleRows]) -> Iterator[ExampleValue]:
    """Show typed field access, null handling and an explicit missing-identifier policy."""
    if not row.value.record_id or not row.value.collection_id:
        raise ValueError("Example mapping requires both identifiers; define a project policy for missing IDs")
    yield ExampleValue(row.value.record_id, row.value.collection_id, row.value.value)


def map_record(measurement: SourceRecord[ExampleValue]) -> tuple[Record, Collection, InCollection]:
    """Mint namespaced identities and build two nodes and their relation."""
    record_id = RecordId(f"example:record:{measurement.value.record_id}")
    collection_id = CollectionId(f"example:collection:{measurement.value.collection_id}")
    return (
        Record(id=record_id, value=measurement.value.value),
        Collection(id=collection_id),
        InCollection(source=record_id, target=collection_id),
    )


NORMALISE = Mapping(
    name="example:normalise-record",
    function=normalise_record,
    evidence=("Illustrative wiring only; replace with the rationale for the actual normalization.",),
)

MAPPING = Mapping(
    name="example:record-collection",
    function=map_record,
    evidence=("Illustrative wiring only; replace with the rationale for the actual mapping.",),
)
