"""Outgoing relation owned beside the sample node."""

from dataclasses import dataclass
from typing import ClassVar

from ..person.node import PersonId
from .node import SampleId


@dataclass(frozen=True)
class FromPerson:
    schema_id: ClassVar[str] = "example:from-person"
    source: SampleId
    target: PersonId
