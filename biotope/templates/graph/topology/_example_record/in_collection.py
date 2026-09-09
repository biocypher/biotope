"""Outgoing relation beside its source node, with typed endpoints."""

from dataclasses import dataclass
from typing import ClassVar

from .._example_collection.node import CollectionId
from .node import RecordId


@dataclass(frozen=True)
class InCollection:
    schema_id: ClassVar[str] = "example:in-collection"
    source: RecordId
    target: CollectionId
