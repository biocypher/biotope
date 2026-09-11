"""The exporter contract, and interpretation context that reaches a database-only reader."""

import csv
import json
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar, NewType

import pytest

from biotope.graph import (
    Audit,
    Capability,
    Evidence,
    GraphView,
    Interpretation,
    Mapping,
    Pipeline,
    QueryContext,
    QueryExample,
    SourceRecord,
    Topology,
    ValidationCheck,
    ValidationResult,
    build,
    output,
)
from biotope.graph.context import CONTEXT_LABEL, build_query_context, check_query_context, decode_text
from biotope.graph.output import BioCypherWriter
from biotope.graph.runtime import RunContext


FindingId = NewType("FindingId", str)

MULTILINE_QUERY = "MATCH (r:StudyResultV1)  // two spaces, one comment\nWHERE r.open_p < 0.05\nRETURN count(r)"
UNVERIFIED_DETAIL = "The contrast orientation was never recorded, so effect signs cannot be compared."


@dataclass(frozen=True)
class Row:
    """A synthetic source row behind one exported finding."""

    key: str
    effect: float
    note: str | None


@dataclass(frozen=True)
class Result:
    """One reported result, retained under the project's own admission rule."""

    schema_id: ClassVar[str] = "study:result.v1"
    id: FindingId
    effect: float = field(metadata={"description": "Log2 fold change, treated over control."})
    strict_p: float = field(metadata={"description": "Adjusted p over the filtered set; the admission rule."})
    open_p: float = field(metadata={"description": "Adjusted p over every tested gene."})
    note: str | None = field(default=None, metadata={"description": "Free-text source comment."})


def make_result(row: SourceRecord[Row]) -> Iterator[Result]:
    """Carry one row into the exported concept, keeping both adjusted p-values."""
    yield Result(FindingId("result:" + row.value.key), row.value.effect, 0.01, 0.04, row.value.note)


def orientation_unknown(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """Record a gap the source cannot close."""
    return ValidationResult.unknown(UNVERIFIED_DETAIL)


RESULTS = Mapping(name="results", function=make_result)

CONTEXT = QueryContext(
    interpretations=(
        Interpretation(
            subject="study:result.v1.strict_p",
            kind="selection",
            statement="Rows were admitted on strict_p < 0.05, which excludes low-count features.",
            alternatives=("study:result.v1.open_p",),
        ),
        Interpretation(
            subject="study:result.v1.effect",
            kind="uncertainty",
            statement="The contrast orientation could not be recovered; do not compare signs across studies.",
        ),
    ),
    capabilities=(
        Capability(
            key="significance",
            question="Which results are significant under either adjustment?",
            concepts=("study:result.v1",),
            limitations=("Only rows passing the strict adjustment were admitted.",),
        ),
        Capability(key="direction", question="Which way does each effect point?"),
    ),
    examples=(
        QueryExample(
            capability="significance",
            language="cypher",
            query=MULTILINE_QUERY,
            expectation="The count under the alternative adjustment, without a rebuild.",
        ),
    ),
)

PIPELINE = Pipeline(
    "context",
    Topology((Result,), ()),
    (),
    (RESULTS,),
    lambda context: context.map(RESULTS, SourceRecord(Row("a", 1.5, None), (Evidence("rows", "v1", "results", "a"),))),
    scope="one synthetic result",
    code_paths=(__file__,),
    query_context=CONTEXT,
    validation_checks=(
        ValidationCheck(
            name="study:orientation",
            function=orientation_unknown,
            capability="direction",
            evidence=("Read from the source methods section.",),
        ),
    ),
    settings={"threshold": 0.05},
)


def delivered_rows(run: Path) -> list[dict[str, str]]:
    """Decode the context rows a database-only consumer would read."""
    part = run / "biocypher" / f"{CONTEXT_LABEL}-part000.csv"
    header = next(csv.reader([(part.with_name(f"{CONTEXT_LABEL}-header.csv")).read_text()]))
    with part.open() as stream:
        return [
            {name: decode_text(value) for name, value in row.items() if isinstance(name, str)}
            for row in csv.DictReader(stream, fieldnames=header)
        ]


def test_exporter_version_is_enforced_before_any_payload_is_read(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})

    def forbidden(context: RunContext) -> None:
        raise AssertionError("the pipeline ran before the exporter was verified")

    monkeypatch.setattr(output, "SUPPORTED_BIOCYPHER", "0.0.0")
    with pytest.raises(build.RunFailed) as failure:
        build.run_pipeline(replace(PIPELINE, run=forbidden), tmp_path / "mismatch")
    message = failure.value.report["error"]
    assert "0.0.0" in message and "pip install" in message
    assert failure.value.report["quality"]["blocked_by"] == "environment.failed"
    assert not (tmp_path / "mismatch/biocypher").exists()

    def absent(name: str) -> str:
        raise output.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(output.importlib.metadata, "version", absent)
    with pytest.raises(ValueError, match="not installed"):
        BioCypherWriter().check_environment()


def test_export_refuses_a_physical_format_it_has_not_tested(tmp_path, monkeypatch):
    class ParquetWriter:
        """Stands in for a writer release whose default output is not CSV."""

        def __init__(self, **kwargs: Any) -> None:
            self.directory = Path(kwargs["output_directory"])

        def write_nodes(self, rows: object) -> bool:
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / "StudyResult-part000.parquet").write_bytes(b"PAR1")
            return True

        def write_edges(self, rows: object) -> bool:
            return True

        def write_import_call(self) -> None:
            return None

    monkeypatch.setattr("biocypher.BioCypher", ParquetWriter)
    context = RunContext(PIPELINE)
    PIPELINE.run(context)
    document = build_query_context(
        PIPELINE,
        schema=context.schema,
        descriptions=PIPELINE.topology.descriptions(),
        labels=output.export_labels(context.schema),
        report={},
    )
    with pytest.raises(ValueError, match="outside the neo4j-admin-csv contract"):
        BioCypherWriter().write(context, tmp_path / "parquet", query_context=document)


def test_database_only_delivery_reconstructs_the_whole_context(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    report = build.run_pipeline(PIPELINE, tmp_path / "run")
    assert json.loads((tmp_path / "run/query_context.json").read_text()) == report["query_context"]

    by_entry: dict[str, list[dict[str, str]]] = {}
    for row in delivered_rows(tmp_path / "run"):
        by_entry.setdefault(row["entry"], []).append(row)

    def one(entry: str, subject: str) -> dict[str, str]:
        return next(row for row in by_entry[entry] if row["subject"] == subject)

    assert one("example", "significance")["statement"] == MULTILINE_QUERY

    assert one("capability", "direction")["detail"] == "unverified"
    assert one("check", "study:orientation")["statement"] == UNVERIFIED_DETAIL
    assert one("check", "study:orientation")["label"] == "direction"
    assert one("check_evidence", "study:orientation")["statement"] == "Read from the source methods section."
    assert one("capability_check", "direction")["statement"] == "study:orientation"

    assert one("capability_limit", "significance")["statement"].startswith("Only rows passing")
    assert one("alternative", "study:result.v1.strict_p")["statement"] == "study:result.v1.open_p"
    assert one("setting", "threshold")["statement"] == "0.05"
    assert one("source", "rows")["statement"] == "v1"
    assert one("property", "study:result.v1.open_p")["statement"].startswith("Adjusted p over every")
    assert one("concept", "study:result.v1")["label"] == "StudyResultV1"
    assert one("uncertainty", "study:result.v1.effect")["statement"].startswith("The contrast orientation")

    assert report["quality"]["measurements"]["population"] == {"study:result.v1": 1}
    assert report["graph_objects"] == {"nodes": 1, "edges": 0}


def test_audit_notes_and_counts_reach_the_database(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})

    def run(context: RunContext) -> None:
        PIPELINE.run(context)
        context.record_audit(
            "read:results",
            inputs="one row per key",
            outputs="one Result per key",
            selection="Keep every eligible row.",
            counts={"read": 2, "kept": 1},
            notes=("One row was withheld pending curation.",),
        )

    build.run_pipeline(replace(PIPELINE, run=run), tmp_path / "audited")
    delivered = delivered_rows(tmp_path / "audited")
    notes = [row["statement"] for row in delivered if row["entry"] == "audit_note"]
    counts = {row["label"]: row["statement"] for row in delivered if row["entry"] == "audit_count"}
    assert notes == ["One row was withheld pending curation."]
    assert counts == {"read": "2", "kept": "1"}


def test_context_references_are_checked_against_the_real_topology():
    schema = PIPELINE.topology.describe()
    descriptions = PIPELINE.topology.descriptions()
    assert [f for f in check_query_context(PIPELINE, schema, descriptions) if f.severity == "error"] == []

    broken = replace(
        PIPELINE,
        query_context=QueryContext(
            interpretations=(
                Interpretation(
                    subject="study:result.v1.absent",
                    kind="statistic",
                    statement="Points at a property that will not exist in the export.",
                ),
                Interpretation(
                    subject="study:result.v1.effect",
                    kind="selection",
                    statement="Claims a reading nothing in this graph supports.",
                    alternatives=("study:result.v1.raw_p",),
                ),
            ),
            examples=(QueryExample(capability="missing", language="cypher", query="MATCH (n) RETURN n"),),
        ),
    )
    messages = [f.message for f in check_query_context(broken, schema, descriptions) if f.severity == "error"]
    assert any("has no property 'absent'" in m for m in messages)
    assert any("capability limitation, not an alternative" in m for m in messages)
    assert any("must name a declared capability" in m for m in messages)

    bare = replace(PIPELINE, query_context=QueryContext(), validation_checks=())
    warnings = {f.code for f in check_query_context(bare, schema, {})}
    assert {"context.unvalidated", "context.no_capabilities", "context.undescribed"} <= warnings
