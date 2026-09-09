"""People are source-local; no cross-study biological identity is asserted."""

from dataclasses import dataclass
from typing import ClassVar, NewType


PersonId = NewType("PersonId", str)


@dataclass(frozen=True)
class Person:
    schema_id: ClassVar[str] = "example:person"
    id: PersonId
    name: str
