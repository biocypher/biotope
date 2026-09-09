"""Mapping consumes two typed inputs and produces three graph object types."""

from biotope.graph import Mapping

from ..sources.study.people.schema import People
from ..sources.study.samples.schema import Samples
from ..topology.person.node import Person, PersonId
from ..topology.sample.from_person import FromPerson
from ..topology.sample.node import Sample, SampleId


SCORE_MULTIPLIER = 2.0
IDENTITY_SCOPE = "fixture"


def map_sample(sample: Samples, person: People) -> tuple[Sample, Person, FromPerson]:
    sample_id = SampleId(f"{IDENTITY_SCOPE}:sample:{sample.sample_id}")
    person_id = PersonId(f"{IDENTITY_SCOPE}:person:{person.person_id}")
    return (
        Sample(id=sample_id, tissue=sample.tissue.lower(), doubled_score=sample.score * SCORE_MULTIPLIER),
        Person(id=person_id, name=person.name),
        FromPerson(source=sample_id, target=person_id),
    )


MAPPING = Mapping(
    "example:sample-person",
    map_sample,
    (Samples, People),
    (Sample, Person, FromPerson),
    requirements=("entity:sample", "entity:person", "relation:from_person"),
    evidence=(
        "Synthetic example; score doubling demonstrates a scientific transform location, not a scientific claim.",
    ),
)
