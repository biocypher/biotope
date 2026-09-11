"""The exporter contract, and interpretation rules that reach a database-only reader."""

import csv
import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, ClassVar, NewType

import pytest

from biotope.graph import (
    Capability,
    Evidence,
    Interpretation,
    Mapping,
    Pipeline,
    QueryContext,
    QueryExample,
    SourceRecord,
    Topology,
    build,
    described,
    output,
)
from biotope.graph.context import CONTEXT_LABEL, build_query_context, check_query_context
from biotope.graph.output import BioCypherWriter
from biotope.graph.runtime import RunContext


FindingId = NewType("FindingId", str)


@dataclass(frozen=True)
class Row:
    """A synthetic source row behind one exported finding."""

    key: str
    effect: float
    note: str | None


@dataclass(frozen=True)
class Result:
    """One reported result, retained under the project's own selection rule."""

    schema_id: ClassVar[str] = "study:result"
    id: FindingId
    effect: float = described("Log2 fold change, treated over control. Sign is the source's, not normalized.")
    strict_p: float = described("Adjusted p-value over the filtered gene set; the admission rule uses this one.")
    open_p: float = described("Adjusted p-value over every tested gene; retained so the other reading is queryable.")
    note: str | None = described("Free-text source comment, absent for most rows.", default=None)


def make_result(row: SourceRecord[Row]) -> Iterator[Result]:
    """Carry one row into the exported concept, keeping both adjusted p-values."""
    yield Result(FindingId("result:" + row.value.key), row.value.effect, 0.01, 0.04, row.value.note)


RESULTS = Mapping(name="results", function=make_result)

CONTEXT = QueryContext(
    interpretations=(
        Interpretation(
            subject="study:result.strict_p",
            kind="selection",
            statement="Rows were admitted on strict_p < 0.05; the filtered set excludes low-expressed genes.",
            alternatives=("study:result.open_p",),
        ),
        Interpretation(
            subject="study:result.effect",
            kind="uncertainty",
            statement="The contrast orientation could not be recovered; do not compare signs across studies.",
        ),
    ),
    capabilities=(
        Capability(
            key="significance",
            question="Which results are significant under either adjustment?",
            concepts=("study:result",),
            limitations=("Only rows passing the strict adjustment were admitted.",),
        ),
    ),
    examples=(
        QueryExample(
            capability="significance",
            language="cypher",
            query="MATCH (r:StudyResult) WHERE r.open_p < 0.05 RETURN count(r)",
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
)


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

    # The writer imports BioCypher inside write(), so patch it where it is looked up.
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


def test_query_context_survives_export_and_database_only_delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    report = build.run_pipeline(PIPELINE, tmp_path / "run")
    document = json.loads((tmp_path / "run/query_context.json").read_text())
    assert document == report["query_context"]
    assert len(document["context_digest"]) == 64

    # Property meaning and the alternative reading travel with the export.
    strict = document["concepts"]["study:result"]["properties"]["strict_p"]
    assert strict["description"].startswith("Adjusted p-value over the filtered gene set")
    selection = next(i for i in document["interpretations"] if i["subject"] == "study:result.strict_p")
    assert selection["alternatives"] == ["study:result.open_p"]
    assert document["capabilities"][0]["state"] == "unchecked"
    assert document["concepts"]["study:result"]["label"] == "StudyResult"

    # A reader with only a Cypher session gets the same rules as queryable rows.
    rows = tmp_path / "run/biocypher" / f"{CONTEXT_LABEL}-part000.csv"
    header = next(csv.reader([(rows.with_name(f"{CONTEXT_LABEL}-header.csv")).read_text()]))
    with rows.open() as stream:
        delivered = list(csv.DictReader(stream, fieldnames=header))
    by_entry = {(row["entry"], row["subject"]): row for row in delivered}
    admission = by_entry[("selection", "study:result.strict_p")]
    assert admission["statement"].startswith("Rows were admitted")
    assert admission["detail"] == "also queryable: study:result.open_p"
    assert ("uncertainty", "study:result.effect") in by_entry
    assert by_entry[("capability", "significance")]["statement"].endswith("[unchecked]")
    assert by_entry[("example", "significance")]["statement"].startswith("MATCH (r:StudyResult)")
    assert by_entry[("concept", "study:result")]["label"] == "StudyResult"
    assert by_entry[("property", "study:result.open_p")]["detail"] == "float"
    # System metadata stays out of the project's own counts.
    assert report["quality"]["measurements"]["population"] == {"study:result": 1}
    assert report["graph_objects"] == {"nodes": 1, "edges": 0}


def test_context_references_are_checked_against_the_real_topology():
    schema = PIPELINE.topology.describe()
    descriptions = PIPELINE.topology.descriptions()
    assert [f for f in check_query_context(PIPELINE, schema, descriptions) if f.severity == "error"] == []

    broken = replace(
        PIPELINE,
        query_context=QueryContext(
            interpretations=(
                Interpretation(
                    subject="study:result.absent",
                    kind="statistic",
                    statement="Points at a property that will not exist in the export.",
                ),
                Interpretation(
                    subject="study:result.effect",
                    kind="selection",
                    statement="Claims a reading nothing in this graph supports.",
                    alternatives=("study:result.raw_p",),
                ),
            ),
            examples=(QueryExample(capability="missing", language="cypher", query="MATCH (n) RETURN n"),),
        ),
    )
    messages = [f.message for f in check_query_context(broken, schema, descriptions) if f.severity == "error"]
    assert any("has no property 'absent'" in m for m in messages)
    assert any("capability limitation, not an alternative" in m for m in messages)
    assert any("must name a declared capability" in m for m in messages)

    warnings = {f.code for f in check_query_context(replace(PIPELINE, query_context=QueryContext()), schema, {})}
    assert {"context.unvalidated", "context.no_capabilities", "context.undescribed"} <= warnings
