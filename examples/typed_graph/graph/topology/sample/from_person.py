"""Outgoing relation owned beside the sample node."""

from dataclasses import dataclass
from typing import ClassVar

from ..person.node import PersonId
from .node import SampleId


@dataclass(frozen=True)
class FromPerson:
    """The sample was taken from this person, as stated by the samples table.

    Many samples to exactly one person. Absence of this edge means the sample
    was excluded, never that the person is unknown to the source.
    """

    schema_id: ClassVar[str] = "example:from-person"
    source: SampleId
    target: PersonId
