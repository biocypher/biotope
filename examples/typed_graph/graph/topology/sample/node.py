"""Selected samples, with an explicitly transformed score."""

from dataclasses import dataclass
from typing import ClassVar, NewType


SampleId = NewType("SampleId", str)


@dataclass(frozen=True)
class Sample:
    schema_id: ClassVar[str] = "example:sample"
    id: SampleId
    tissue: str
    doubled_score: float
