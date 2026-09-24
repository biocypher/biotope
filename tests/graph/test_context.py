"""Retired query-context declarations and database delivery; removed with the context API."""

import json
from dataclasses import dataclass, field, replace
from typing import ClassVar, NewType

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
    build_query_context,
    check_query_context,
    context_rows,
)
from biotope.graph.runtime import RunContext


FindingId = NewType("FindingId", str)
StudyId = NewType("StudyId", str)

MULTILINE_QUERY = "MATCH (r:ResultV1)  // two spaces, one comment\nWHERE r.open_p < 0.05\nRETURN count(r)"
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

    header = (tmp_path / "vandal/biocypher/ResultV1-header.csv").read_text()
    assert "effect" in header
    provenance = json.loads((tmp_path / "vandal/provenance.json").read_text())
    assert all(record["evidence"] for record in provenance["records"])
    assert report["audits"][0]["counts"] == {"retained": 1}
    assert "query_context" not in report
