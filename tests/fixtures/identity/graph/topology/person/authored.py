from dataclasses import dataclass, field
from typing import ClassVar

from ..paper.node import PaperId
from .node import PersonId


@dataclass(frozen=True)
class Authored:
    """The person is an author of the paper, as a publication source lists it."""

    schema_id: ClassVar[str] = "fixture:authored"
    source: PersonId
    target: PaperId
    position: int | None = field(metadata={"description": "The person's position in the author list, from 1."})
