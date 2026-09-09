"""Illustrative pure transformation; replace identities and policies before use."""

from biotope.graph import Mapping

from ..sources._example.schema import ExampleRow
from ..topology._example_collection.node import Collection, CollectionId
from ..topology._example_record.in_collection import InCollection
from ..topology._example_record.node import Record, RecordId


def map_record(row: ExampleRow) -> tuple[Record, Collection, InCollection]:
    """Show typed field access, explicit identity and nullable property handling."""
    if not row.record_id or not row.collection_id:
        raise ValueError("Example mapping requires both identifiers; define a project policy for missing IDs")
    record_id = RecordId(f"example:record:{row.record_id}")
    collection_id = CollectionId(f"example:collection:{row.collection_id}")
    return (
        Record(id=record_id, value=row.value),
        Collection(id=collection_id),
        InCollection(source=record_id, target=collection_id),
    )


MAPPING = Mapping(
    name="example:record-collection",
    function=map_record,
    inputs=(ExampleRow,),
    outputs=(Record, Collection, InCollection),
    evidence=("Illustrative wiring only; replace with the rationale for the actual mapping.",),
)
