"""Executable acceptance for the capabilities this graph claims."""

import csv

from biotope.graph import Audit, GraphView, ValidationCheck, ValidationResult

from .paths import PROJECT_ROOT
from .topology.sample.from_person import FromPerson
from .topology.sample.node import Sample


DECLARED_MULTIPLIER = 2.0
"""The factor query_context.py publishes, deliberately not the pipeline's constant."""


def _rows(name: str) -> list[dict[str, str]]:
    with (PROJECT_ROOT / "raw" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _source_key(identity: str) -> str:
    return identity.rsplit(":", 1)[-1]


def sample_ownership_matches_source(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """Every sample must reach the person the source assigned it, and no other."""
    people = {row["person_id"] for row in _rows("people.csv")}
    expected = {(row["sample_id"], row["person_id"]) for row in _rows("samples.csv") if row["person_id"] in people}
    found = {(_source_key(edge.source), _source_key(edge.target)) for edge in view.records(FromPerson)}
    if found != expected:
        return ValidationResult.wrong(
            f"Ownership differs from the source: missing {sorted(expected - found)}, "
            f"unexpected {sorted(found - expected)}.",
            expected=len(expected),
            found=len(found),
        )
    return ValidationResult.ok(f"All {len(expected)} source sample-person pairs are present.", pairs=len(expected))


def scores_match_the_published_transform(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """Every stored score must equal the source score times the published factor."""
    expected = {row["sample_id"]: float(row["score"]) * DECLARED_MULTIPLIER for row in _rows("samples.csv")}
    wrong = {
        sample.id: (sample.doubled_score, expected[_source_key(sample.id)])
        for sample in view.records(Sample)
        if _source_key(sample.id) in expected and sample.doubled_score != expected[_source_key(sample.id)]
    }
    if wrong:
        return ValidationResult.wrong(
            f"Stored scores contradict the published transform of x{DECLARED_MULTIPLIER}: {sorted(wrong)}.",
            mismatched=len(wrong),
        )
    return ValidationResult.ok(f"Every stored score is the source value x{DECLARED_MULTIPLIER}.")


def scores_are_comparable_across_tissues(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """Comparing scores between tissues needs a scale the source never states."""
    rows = _rows("samples.csv")
    declared = sorted(rows[0]) if rows else []
    scale = [name for name in declared if "unit" in name.lower() or "scale" in name.lower()]
    if scale:
        return ValidationResult.ok(f"The source declares a scale in {scale}.")
    return ValidationResult.unknown(
        f"samples.csv declares {declared} and no unit or scale column, so scores from "
        "different tissues cannot be shown to share one scale. Comparisons within a tissue "
        "remain valid."
    )


VALIDATION_CHECKS = (
    ValidationCheck(
        name="example:sample-ownership",
        function=sample_ownership_matches_source,
        capability="samples-per-person",
        evidence=("Pairs read from raw/samples.csv and raw/people.csv.",),
    ),
    ValidationCheck(
        name="example:published-transform",
        function=scores_match_the_published_transform,
        capability="score-comparison",
        evidence=("Source scores from raw/samples.csv against the factor in query_context.py.",),
    ),
    ValidationCheck(
        name="example:cross-tissue-scale",
        function=scores_are_comparable_across_tissues,
        capability="cross-tissue-scores",
        evidence=("Column names declared by raw/samples.csv.",),
    ),
)
