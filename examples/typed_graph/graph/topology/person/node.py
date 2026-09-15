"""People are source-local; no cross-study biological identity is asserted."""

from dataclasses import dataclass, field
from typing import ClassVar, NewType


PersonId = NewType("PersonId", str)


@dataclass(frozen=True)
class Person:
    """One person referenced by at least one selected sample.

    Identity is scoped to this study's person_id. Two people with the same name
    in different studies are different nodes, and no attempt is made to link them.
    """

    schema_id: ClassVar[str] = "example:person"
    id: PersonId
    name: str = field(metadata={"description": "The person's name exactly as the source spells it; not an identifier."})
