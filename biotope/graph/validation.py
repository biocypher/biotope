"""Project-declared checks of the built graph, run between integrity and export.

Integrity and quality can only measure what the pipeline emitted. Comparing the
graph with an expectation from outside it is what these checks add.
"""

from __future__ import annotations

from typing import Any

from biotope.graph.contracts import Audit, GraphView, Pipeline, ValidationResult
from biotope.graph.reports import Finding, FindingSink, Phase


UNCHECKED = "unchecked"
ABSENT = "absent"


def _outcome(check_states: list[str]) -> str:
    if not check_states:
        return UNCHECKED
    for state in ("failed", "unverified"):
        if state in check_states:
            return state
    return "passed"


def run_validation(
    pipeline: Pipeline,
    view: GraphView,
    audits: tuple[Audit, ...],
    *,
    phase: Phase | None = None,
    on_finding: FindingSink | None = None,
) -> dict[str, Any]:
    """Execute every declared check once and report per-check and per-capability states.

    A check that raises has not passed: its failure is recorded like any other,
    with the exception text, so a broken check can never be mistaken for a green
    one. Only ``failed`` blocks export; ``unverified`` leaves the capabilities
    that depend on it unresolved and keeps everything else usable.
    """
    findings: list[Finding] = []

    def add(finding: Finding) -> None:
        findings.append(finding)
        if on_finding:
            on_finding(finding)

    results: list[dict[str, Any]] = []
    for check in pipeline.validation_checks:
        if phase:
            phase("Validation: " + check.name)
        try:
            outcome = check.function(view, audits)
            if not isinstance(outcome, ValidationResult):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise TypeError(f"returned {type(outcome).__name__}, not a ValidationResult")
        except Exception as exc:
            outcome = ValidationResult("failed", f"The check itself failed: {exc}")
        results.append(
            {
                "name": check.name,
                "capability": check.capability,
                "state": outcome.state,
                "detail": outcome.detail,
                "measurements": outcome.measurements,
                "evidence": list(check.evidence),
            }
        )
        if outcome.state == "failed":
            add(Finding("validation.failed", "error", check.name, outcome.detail))
        elif outcome.state == "unverified":
            add(Finding("validation.unverified", "warning", check.name, outcome.detail))

    capabilities: dict[str, Any] = {}
    for capability in pipeline.query_context.capabilities:
        bound = [item for item in results if item["capability"] == capability.key]
        state = _outcome([item["state"] for item in bound])
        capabilities[capability.key] = {
            "question": capability.question,
            "state": "supported" if state == "passed" else state,
            "checks": [item["name"] for item in bound],
            "limitations": list(capability.limitations),
        }
        if state == UNCHECKED:
            add(
                Finding(
                    "validation.unchecked_capability",
                    "warning",
                    capability.key,
                    "This question family is claimed but no validation check tests it: " + capability.question,
                )
            )

    state = _outcome([item["state"] for item in results])
    if state == UNCHECKED:
        state = ABSENT
        add(
            Finding(
                "validation.absent",
                "warning",
                pipeline.name,
                "No project validation checks ran. Structural checks cannot see evidence the "
                "pipeline never emitted, so this graph's fitness for its purpose is unverified.",
            )
        )
    reasons = {
        "passed": "Every declared check returned a pass. Nothing else about answerability is established.",
        "failed": "At least one declared expectation is contradicted by the graph; export is blocked.",
        "unverified": "Some expectations could not be established; their capabilities stay unresolved.",
        ABSENT: "No checks were declared; nothing about answerability was established.",
    }
    return {
        "state": state,
        "reason": reasons[state],
        "checks": results,
        "capabilities": capabilities,
        "findings": [finding.to_json() for finding in findings],
    }
