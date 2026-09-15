"""Normalization and graph construction as two separately checked typed steps.

Split here to demonstrate the pattern. One source that maps cleanly onto its concepts
can skip the intermediate and annotate ``map_sample`` with ``SourceRecord[Samples]``.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from biotope.graph import Mapping, SourceRecord

from ..sources.study.people.schema import People
from ..sources.study.samples.schema import Samples
from ..topology.person.node import Person, PersonId
from ..topology.sample.from_person import FromPerson
from ..topology.sample.node import Sample, SampleId


SCORE_MULTIPLIER = 2.0
IDENTITY_SCOPE = "fixture"


@dataclass(frozen=True)
class Measurement:
    """One normalized sample row: source decisions resolved, no identity minted yet."""

    sample_id: str
    person_id: str
    tissue: str
    score: float


def normalise_sample(sample: SourceRecord[Samples]) -> Iterator[Measurement]:
    """Resolve the project's casing and unit decisions on a single source row."""
    row = sample.value
    yield Measurement(
        sample_id=row.sample_id,
        person_id=row.person_id,
        tissue=row.tissue.lower(),
        score=row.score * SCORE_MULTIPLIER,
    )


def map_sample(
    measurement: SourceRecord[Measurement], person: SourceRecord[People]
) -> tuple[Sample, Person, FromPerson]:
    """Mint namespaced identities and build the graph objects for one measurement."""
    sample_id = SampleId(f"{IDENTITY_SCOPE}:sample:{measurement.value.sample_id}")
    person_id = PersonId(f"{IDENTITY_SCOPE}:person:{person.value.person_id}")
    return (
        Sample(id=sample_id, tissue=measurement.value.tissue, doubled_score=measurement.value.score),
        Person(id=person_id, name=person.value.name),
        FromPerson(source=sample_id, target=person_id),
    )


NORMALISE = Mapping(
    name="example:normalise-sample",
    function=normalise_sample,
    evidence=(
        "Synthetic example; score doubling demonstrates a scientific transform location, not a scientific claim.",
    ),
)

MAPPING = Mapping(
    name="example:sample-person",
    function=map_sample,
    requirements=("entity:sample", "entity:person", "relation:from_person"),
    evidence=("Synthetic example; sample and person identities stay source-local.",),
)
