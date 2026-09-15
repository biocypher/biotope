"""The exporter contract, and interpretation context that reaches a database-only reader."""

import csv
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar, NewType

import pyarrow.parquet
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
from biotope.graph.context import (
    CONTEXT_LABEL,
    build_query_context,
    check_query_context,
    context_rows,
    decode_text,
)
from biotope.graph.output import BioCypherWriter
from biotope.graph.runtime import RunContext


FindingId = NewType("FindingId", str)
StudyId = NewType("StudyId", str)

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


@dataclass(frozen=True)
class Study:
    """The study that reported a result."""

    schema_id: ClassVar[str] = "study:source"
    id: StudyId
    cohort: str = field(metadata={"description": "Recruitment site and inclusion criteria, verbatim."})


@dataclass(frozen=True)
class ReportedBy:
    """The result was reported by this study, under that study's own protocol."""

    schema_id: ClassVar[str] = "study:reported-by"
    source: FindingId
    target: StudyId


def make_result(row: SourceRecord[Row]) -> tuple[Result, Study, ReportedBy]:
    """Carry one row into the exported concepts and the relationship between them."""
    finding = FindingId("result:" + row.value.key)
    study = StudyId("study:one")
    return (
        Result(finding, row.value.effect, 0.01, 0.04, row.value.note),
        Study(study, "single site, adults"),
        ReportedBy(finding, study),
    )


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
        Capability(
            key="provenance",
            question="Which study reported a given result?",
            concepts=("study:reported-by", "study:source.cohort"),
        ),
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
    Topology((Result, Study), (ReportedBy,)),
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

    monkeypatch.setattr(output, "SUPPORTED_BIOCYPHER", ((0, 99), (0, 100)))
    with pytest.raises(build.RunFailed) as failure:
        build.run_pipeline(replace(PIPELINE, run=forbidden), tmp_path / "mismatch")
    message = failure.value.report["error"]
    assert ">=0.99,<0.100" in message and "pip install" in message
    assert failure.value.report["quality"]["blocked_by"] == "environment.failed"
    assert not (tmp_path / "mismatch/biocypher").exists()

    def absent(name: str) -> str:
        raise output.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(output.importlib.metadata, "version", absent)
    with pytest.raises(ValueError, match="not installed"):
        BioCypherWriter().check_environment()


def test_export_refuses_output_the_declared_format_does_not_cover(tmp_path, monkeypatch):
    class ParquetWriter:
        """Stands in for a writer that ignores the format the config selected."""

        def __init__(self, **kwargs: Any) -> None:
            self.directory = Path(kwargs["output_directory"])

        def write_nodes(self, rows: object) -> bool:
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / "StudyResultV1-part000.parquet").write_bytes(b"PAR1")
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
    with pytest.raises(ValueError, match="declared neo4j-admin-csv contract does not cover"):
        BioCypherWriter("csv").write(context, tmp_path / "mismatch", query_context=document)

    with pytest.raises(ValueError, match="Unsupported export format"):
        BioCypherWriter("avro")


def test_parquet_is_a_supported_declared_format(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    report = build.run_pipeline(PIPELINE, tmp_path / "pq", writer=BioCypherWriter("parquet"))
    assert report["exporter"]["format"] == "neo4j-admin-parquet"

    written = sorted(p.name for p in (tmp_path / "pq/biocypher").iterdir())
    assert written == [
        "BiotopeQueryContext-part000.parquet",
        "StudyReportedBy-part000.parquet",
        "StudyResultV1-part000.parquet",
        "StudySource-part000.parquet",
        "neo4j-admin-import-call.sh",
    ]

    # The interpretation context still reaches a reader, through the other format.
    table = pyarrow.parquet.read_table(tmp_path / "pq/biocypher/BiotopeQueryContext-part000.parquet")
    rows = table.to_pylist()
    example = next(row for row in rows if row["entry"] == "example")
    assert decode_text(example["statement"]) == MULTILINE_QUERY
    assert (tmp_path / "pq/query_context.json").is_file()


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

    # Relationship endpoints and capability bindings reach the database too.
    assert one("concept_source", "study:reported-by")["statement"] == "study:result.v1"
    assert one("concept_target", "study:reported-by")["statement"] == "study:source"
    bound = {row["statement"] for row in by_entry["capability_concept"] if row["subject"] == "provenance"}
    assert bound == {"study:reported-by", "study:source.cohort"}

    assert report["quality"]["measurements"]["population"] == {
        "study:result.v1": 1,
        "study:source": 1,
        "study:reported-by": 1,
    }
    assert report["graph_objects"] == {"nodes": 2, "edges": 1}


def test_database_rows_change_when_a_capability_binding_changes():
    def rows(pipeline: Pipeline) -> set[frozenset[tuple[str, object]]]:
        context = RunContext(pipeline)
        pipeline.run(context)
        document = build_query_context(
            pipeline,
            schema=context.schema,
            descriptions=pipeline.topology.descriptions(),
            labels=output.export_labels(context.schema),
            report={},
        )
        return {frozenset(properties.items()) for _, properties in context_rows(document)}

    rebound = tuple(
        replace(item, concepts=("study:result.v1.open_p",)) if item.key == "significance" else item
        for item in CONTEXT.capabilities
    )
    assert rows(PIPELINE) != rows(replace(PIPELINE, query_context=replace(CONTEXT, capabilities=rebound)))


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


def test_a_vandalising_check_cannot_reach_the_exported_files(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})

    def vandalise(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
        view.concepts["study:result.v1"]["properties"].pop("effect")
        audits[0].counts["retained"] = 900
        return ValidationResult.ok("Reported success after editing the schema and the audit.")

    def run(context: RunContext) -> None:
        PIPELINE.run(context)
        context.record_audit(
            "read:results",
            inputs="one row",
            outputs="one Result",
            selection="Keep every eligible row.",
            counts={"retained": 1},
        )

    pipeline = replace(
        PIPELINE,
        run=run,
        validation_checks=(ValidationCheck("study:vandal", vandalise, "significance"),),
    )
    report = build.run_pipeline(pipeline, tmp_path / "vandal")
    assert report["validation"]["state"] == "passed"

    header = (tmp_path / "vandal/biocypher/StudyResultV1-header.csv").read_text()
    assert "effect" in header
    provenance = (tmp_path / "vandal/provenance.jsonl").read_text().splitlines()
    assert all(json.loads(line)["evidence"] for line in provenance)
    assert report["audits"][0]["counts"] == {"retained": 1}
    assert report["query_context"]["selection"]["audits"][0]["counts"] == {"retained": 1}
    assert "effect" in report["query_context"]["concepts"]["study:result.v1"]["properties"]
