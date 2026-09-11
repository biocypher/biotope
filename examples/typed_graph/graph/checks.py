"""Executable acceptance: does this graph answer what it claims to answer?

Each check derives its expectation from the source, not from the pipeline. A
check that recomputes the build's own logic proves the code is self-consistent
and nothing else; it cannot notice a row the pipeline never emitted, which is
exactly the failure these checks exist to catch. So the readers here are plain
``csv`` calls, deliberately independent of ``graph/sources``.
"""

import csv

from biotope.graph import Audit, GraphView, ValidationCheck, ValidationResult

from .paths import PROJECT_ROOT
from .topology.person.node import Person
from .topology.sample.from_person import FromPerson
from .topology.sample.node import Sample


def _rows(name: str) -> list[dict[str, str]]:
    """Read one raw table with a reader the pipeline does not use."""
    with (PROJECT_ROOT / "raw" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def matched_samples_are_complete(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """Every source sample with a known person must be present, and no others."""
    people = {row["person_id"] for row in _rows("people.csv")}
    expected = {row["sample_id"] for row in _rows("samples.csv") if row["person_id"] in people}
    found = {sample.id.split(":")[-1] for sample in view.records(Sample)}
    if found != expected:
        return ValidationResult.wrong(
            f"Matched samples differ from the source: {sorted(expected - found)} missing, "
            f"{sorted(found - expected)} unexpected.",
            expected=len(expected),
            found=len(found),
        )
    return ValidationResult.ok(f"All {len(expected)} matched source samples are present.", samples=len(expected))


def every_sample_reaches_its_person(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """The documented join must actually traverse: no sample may be stranded."""
    people = {person.id for person in view.records(Person)}
    edges = {(edge.source, edge.target) for edge in view.records(FromPerson)}
    stranded = [sample.id for sample in view.records(Sample) if not any(s == sample.id for s, _ in edges)]
    unresolved = sorted({target for _, target in edges if target not in people})
    if stranded or unresolved:
        return ValidationResult.wrong(
            f"Join coverage is incomplete: {len(stranded)} samples without a person edge, "
            f"{len(unresolved)} edges to an absent person.",
            stranded=len(stranded),
            unresolved=len(unresolved),
        )
    return ValidationResult.ok(f"All {len(edges)} sample-person joins resolve.", joins=len(edges))


def raw_scores_are_recoverable(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """A question about source score magnitude cannot be answered from this graph."""
    return ValidationResult.unknown(
        "Only doubled_score is stored, so absolute source scores cannot be recovered by any query. "
        "Comparisons between samples remain valid; statements about raw magnitude do not."
    )


VALIDATION_CHECKS = (
    ValidationCheck(
        name="example:matched-samples-complete",
        function=matched_samples_are_complete,
        capability="samples-per-person",
        evidence=("Expectation read straight from raw/samples.csv and raw/people.csv.",),
    ),
    ValidationCheck(
        name="example:join-coverage",
        function=every_sample_reaches_its_person,
        capability="samples-per-person",
        evidence=("Exercises the join the documented query example depends on.",),
    ),
    ValidationCheck(
        name="example:raw-score-recoverable",
        function=raw_scores_are_recoverable,
        capability="score-comparison",
        evidence=("Records a known gap rather than leaving the limitation to the reader.",),
    ),
)
