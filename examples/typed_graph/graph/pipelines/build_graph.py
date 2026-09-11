"""Explicit many-to-one join; people are held in memory, samples stream."""

from biotope.graph import Pipeline, RunContext, SourceRecord

from ..checks import VALIDATION_CHECKS
from ..mappings import MAPPINGS
from ..mappings.samples import IDENTITY_SCOPE, MAPPING, NORMALISE, SCORE_MULTIPLIER
from ..paths import GRAPH_ROOT, PROJECT_ROOT
from ..query_context import QUERY_CONTEXT
from ..sources import PEOPLE, SAMPLES, SOURCES
from ..sources.study.people.loader import load as load_people
from ..sources.study.people.schema import People
from ..sources.study.samples.loader import load as load_samples
from ..topology import TOPOLOGY


def build(context: RunContext) -> None:
    people: dict[str, SourceRecord[People]] = {}
    for person in context.load(PEOPLE, load_people, PROJECT_ROOT / "raw/people.csv"):
        if person.value.person_id in people:
            raise ValueError(f"people.person_id must be unique: {person.value.person_id}")
        people[person.value.person_id] = person
    matched: set[str] = set()
    read = kept = 0
    for sample in context.load(SAMPLES, load_samples, PROJECT_ROOT / "raw/samples.csv"):
        read += 1
        # Normalization first; the intermediate keeps its type through the join.
        for measurement in context.apply(NORMALISE, sample):
            person = people.get(measurement.value.person_id)
            if person is None:
                context.exclude("unmatched_sample", measurement.evidence)
                continue
            matched.add(person.value.person_id)
            kept += 1
            context.map(MAPPING, measurement, person)
    for key, person in people.items():
        if key not in matched:
            context.exclude("unused_person", person.evidence)
    context.record_audit(
        "join:samples-to-people",
        inputs="one row per sample_id in samples.csv",
        outputs="one Sample, one FromPerson and a shared Person per matched sample",
        selection="Keep a sample when its person_id has a row in people.csv; drop it otherwise.",
        counts={
            "people_read": len(people),
            "people_matched": len(matched),
            "samples_read": read,
            "samples_kept": kept,
        },
    )


PIPELINE = Pipeline(
    name="example:sample-people",
    topology=TOPOLOGY,
    sources=SOURCES,
    mappings=MAPPINGS,
    run=build,
    scope=(
        "Synthetic samples with known people; one sample per matched sample_id and one person per referenced person_id."
    ),
    code_paths=tuple(
        GRAPH_ROOT / path
        for path in (
            "__init__.py",
            "paths.py",
            "checks.py",
            "query_context.py",
            "sources",
            "topology",
            "mappings",
            "pipelines",
        )
    ),
    intent=PROJECT_ROOT / "project.yaml",
    requirements={
        "entity:sample": "example:sample",
        "entity:person": "example:person",
        "relation:from_person": "example:from-person",
    },
    policies={
        "unmatched_sample": "Exclude samples without a person_id match; many samples to exactly one person.",
        "unused_person": "Exclude people without selected samples.",
    },
    settings={"score_multiplier": SCORE_MULTIPLIER, "identity_scope": IDENTITY_SCOPE},
    variability="Fixed checked-in synthetic inputs, version fixture-v1; deterministic content.",
    validation_checks=VALIDATION_CHECKS,
    query_context=QUERY_CONTEXT,
)
