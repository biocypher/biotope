"""Selected samples, with an explicitly transformed score."""

from dataclasses import dataclass
from typing import ClassVar, NewType

from biotope.graph import described


SampleId = NewType("SampleId", str)


@dataclass(frozen=True)
class Sample:
    """One synthetic sample that matched a known person.

    A sample whose person_id has no row in people.csv is excluded, so this
    concept is not the complete sample list of the source.
    """

    schema_id: ClassVar[str] = "example:sample"
    id: SampleId
    tissue: str = described("Source tissue label, lowercased. Free text, not an ontology term.")
    doubled_score: float = described(
        "The source score multiplied by the project's fixed multiplier. A derived value, "
        "not a measurement; the source score is not retained separately."
    )
