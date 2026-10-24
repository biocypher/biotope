from dataclasses import dataclass, field
from typing import ClassVar, NewType


PersonId = NewType("PersonId", str)


@dataclass(frozen=True)
class Person:
    """An invented researcher, one entity across the roster, the directory and profile pages."""

    schema_id: ClassVar[str] = "fixture:person"
    id: PersonId
    name: str = field(metadata={"description": "The person's name as the first source in the declared order gives it."})
    roster: str | None = field(metadata={"description": "The person's record ID in the roster."})
    orcid: str | None = field(metadata={"description": "The person's ORCID iD."})
    emails: list[str] = field(metadata={"description": "Every email address a source gives for the person."})
