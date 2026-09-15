"""Selected samples, with an explicitly transformed score."""

from dataclasses import dataclass, field
from typing import ClassVar, NewType


SampleId = NewType("SampleId", str)


@dataclass(frozen=True)
class Sample:
    """One synthetic sample that matched a known person.

    A sample whose person_id has no row in people.csv is excluded, so this
    concept is not the complete sample list of the source.
    """

    schema_id: ClassVar[str] = "example:sample"
    id: SampleId
    tissue: str = field(metadata={"description": "Source tissue label, lowercased. Free text, not an ontology term."})
    doubled_score: float = field(
        metadata={
            "description": (
                "The source score multiplied by 2.0. A derived value, not a measurement; "
                "the source score is not retained separately."
            )
        }
    )
