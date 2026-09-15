"""Illustrative second node with a distinct identifier type."""

from dataclasses import dataclass
from typing import ClassVar, NewType


CollectionId = NewType("CollectionId", str)


@dataclass(frozen=True)
class Collection:
    schema_id: ClassVar[str] = "example:collection"
    display_name: ClassVar[str] = "Collection"
    id: CollectionId
