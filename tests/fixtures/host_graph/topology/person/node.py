from dataclasses import dataclass
from typing import ClassVar, NewType


PersonId = NewType("PersonId", str)


@dataclass(frozen=True)
class Person:
    schema_id: ClassVar[str] = "host:person"
    id: PersonId
    name: str
