"""Structured diagnostics shared by checking, execution and presentation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal


Phase = Callable[[str], None]
Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Location:
    """A file location, with one-based lines and columns when known."""

    path: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class Finding:
    """An observation with a stable identity and bounded supporting examples."""

    code: str
    severity: Severity
    subject: str
    message: str
    location: Location | None = None
    examples: tuple[dict[str, object], ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {**asdict(self), "examples": list(self.examples)}


FindingSink = Callable[[Finding], None]


@dataclass(frozen=True)
class CheckResult:
    """Completion of one independent stage; skipped never means passed."""

    name: str
    state: Literal["passed", "failed", "skipped"]
    reason: str = ""


@dataclass
class DefinitionReport:
    """Definition evidence plus machine-addressable findings and stage states."""

    data: dict[str, Any] = field(default_factory=dict[str, Any])
    findings: list[Finding] = field(default_factory=list[Finding])
    checks: list[CheckResult] = field(default_factory=list[CheckResult])

    def to_json(self) -> dict[str, Any]:
        return {
            **self.data,
            "schema_version": 1,
            "report_kind": "biotope.definitions",
            "state": "failed" if any(f.severity == "error" for f in self.findings) else "checked",
            "findings": [f.to_json() for f in self.findings],
            "checks": [asdict(c) for c in self.checks],
        }


@dataclass
class QualityReport:
    """Measurements of final graph objects, never a scientific quality score."""

    measurements: dict[str, Any] = field(default_factory=dict[str, Any])
    findings: list[Finding] = field(default_factory=list[Finding])

    def to_json(self) -> dict[str, Any]:
        return {
            "state": "complete",
            "measurements": self.measurements,
            "findings": [f.to_json() for f in self.findings],
            "examples_method": (
                "Up to three first-encountered distinct non-null values; illustrative, not representative."
            ),
            "example_limits": {
                "record_ids": 3,
                "mapping_references": 3,
                "provenance_references": 3,
                "property_values": 3,
                "string_characters": 160,
                "list_items": 5,
            },
        }


class CheckFailed(ValueError):
    """Retain all completed checks when definitions cannot be executed."""

    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__("\n".join(f["message"] for f in report["findings"] if f["severity"] == "error"))


class PythonCheckFailed(ValueError):
    """Preserve the checker's diagnostics instead of parsing a rendered message."""

    def __init__(self, findings: list[Finding]):
        self.findings = findings
        super().__init__("Static checking failed:\n" + "\n".join(f.message for f in findings))
