from dataclasses import dataclass, field
from typing import ClassVar, NewType


PaperId = NewType("PaperId", str)


@dataclass(frozen=True)
class Paper:
    """An invented paper, identified by its DOI."""

    schema_id: ClassVar[str] = "fixture:paper"
    id: PaperId
    title: str = field(
        metadata={"description": "The paper's title as the first source in the declared order gives it."}
    )
