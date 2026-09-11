"""Executable acceptance: does this graph answer what it claims to answer?

Derive every expectation from the source, a published figure or a curated
answer. A check that recomputes the pipeline's own logic shows the code is
self-consistent and nothing more; it cannot notice a row the pipeline never
emitted, which is the failure these checks exist to catch. So read the source
here with a plain reader, independently of ``graph/sources``.

A failed check blocks the export. An unverified one records missing knowledge:
its capability stays unresolved while every other capability remains usable.
"""

from biotope.graph import Audit, GraphView, ValidationCheck, ValidationResult


def example_check(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """Compare one independently derived expectation with what the graph holds."""
    return ValidationResult.unknown("Replace this with a real expectation before research use.")


VALIDATION_CHECKS: tuple[ValidationCheck, ...] = (
    # ValidationCheck(
    #     name="<project>:<what-it-protects>",
    #     function=example_check,
    #     capability="<capability key from query_context.py>",
    #     evidence=("Where the expectation came from.",),
    # ),
)
