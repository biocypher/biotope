"""Exporter contract, actual Neo4j CSV values, readable labels and collision disambiguation."""

import csv
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar, NewType

import pyarrow.parquet
import pytest
import yaml

from biotope.graph import Evidence, Mapping, Pipeline, SourceRecord, Topology, build, output
from biotope.graph.output import ARRAY_DELIMITER, BioCypherWriter, export_labels
from biotope.graph.runtime import RunContext


ItemId = NewType("ItemId", str)
OtherId = NewType("OtherId", str)


@dataclass(frozen=True)
class ItemRow:
    """A synthetic source row behind both exported concepts."""

    identity: str
    label: str
    aliases: list[str]


@dataclass(frozen=True)
class Item:
    schema_id: ClassVar[str] = "study:item"
    id: ItemId
    label: str
    aliases: list[str]


@dataclass(frozen=True)
class Other:
    schema_id: ClassVar[str] = "study:ITEM"
    id: OtherId
    note: str | None


def make_item(row: SourceRecord[ItemRow]) -> Iterator[Item]:
    """Carry the source row into the exported item concept."""
    yield Item(ItemId(row.value.identity), row.value.label, row.value.aliases)


def make_other(row: SourceRecord[ItemRow]) -> Iterator[Other]:
    """Produce the concept whose readable label collides with the item's."""
    yield Other(OtherId(row.value.identity), None)


ITEMS = Mapping(name="items", function=make_item)
OTHERS = Mapping(name="others", function=make_other)


FindingId = NewType("FindingId", str)
StudyId = NewType("StudyId", str)


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


RESULTS = Mapping(name="results", function=make_result)

PIPELINE = Pipeline(
    "context",
    Topology((Result, Study), (ReportedBy,)),
    (),
    (RESULTS,),
    lambda context: context.map(RESULTS, SourceRecord(Row("a", 1.5, None), (Evidence("rows", "v1", "results", "a"),))),
    scope="one synthetic result",
    code_paths=(__file__,),
    settings={"threshold": 0.05},
)


def test_biocypher_labels_and_string_values_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = Pipeline(
        "export",
        Topology((Item,), ()),
        (),
        (ITEMS, OTHERS),
        lambda ctx: None,
        scope="CSV representation",
        code_paths=(__file__,),
    )
    context = RunContext(pipeline)
    evidence = (Evidence("items", "v1", "items", "key:1"),)
    value = ItemRow("item:1", 'Text "quoted", and | delimited', ['alias "quoted"', "with, comma"])
    context.map(ITEMS, SourceRecord(value, evidence))
    BioCypherWriter().write(context, tmp_path / "readable")
    output = tmp_path / "readable/biocypher/Item-part000.csv"
    header = next(csv.reader([(output.parent / "Item-header.csv").read_text()]))
    with output.open() as stream:
        row = next(csv.DictReader(stream, fieldnames=header))
    assert row["label"] == value.label
    assert row["aliases:string[]"].split(ARRAY_DELIMITER) == value.aliases
    # Headless export retains the declared concept label.
    assert row[":LABEL"] == "Item"
    # A literal array separator cannot be represented unambiguously; reject it.
    invalid = RunContext(pipeline)
    invalid.map(ITEMS, SourceRecord(replace(value, aliases=[f"a{ARRAY_DELIMITER}b"]), evidence))
    with pytest.raises(ValueError, match="string-list separator"):
        BioCypherWriter().write(invalid, tmp_path / "invalid")

    colliding = RunContext(replace(pipeline, topology=Topology((Item, Other), ())))
    colliding.map(ITEMS, SourceRecord(value, evidence))
    colliding.map(OTHERS, SourceRecord(replace(value, identity="other:1"), evidence))
    BioCypherWriter().write(colliding, tmp_path / "colliding")
    schema = yaml.safe_load((tmp_path / "colliding/schema_config.yaml").read_text())
    labels = {item["input_label"]: label for label, item in schema.items()}
    assert len({v for k, v in labels.items() if k.startswith("study:")}) == 2
    # A null property stays an empty cell rather than a literal "None".
    other = tmp_path / "colliding/biocypher" / f"{labels['study:ITEM']}-part000.csv"
    other_header = next(csv.reader([(other.with_name(other.name.replace("part000", "header"))).read_text()]))
    with other.open() as stream:
        assert next(csv.DictReader(stream, fieldnames=other_header))["note"] == ""
    # Both labels must survive the writer's own PascalCase conversion.
    actual = set()
    for path in (tmp_path / "colliding/biocypher").glob("*-part000.csv"):
        with path.open() as stream:
            actual.update(next(csv.reader(stream))[-1].split("|"))
    assert actual == set(labels.values())


def test_export_labels_drop_the_namespace_and_widen_only_under_collision():
    assert export_labels(["ot:drug", "ot:drug-has-mechanism"]) == {
        "ot:drug": "Drug",
        "ot:drug-has-mechanism": "DrugHasMechanism",
    }
    # The namespace is the disambiguator, so a shared local name brings it back for the whole group.
    assert export_labels(["gtex:sample", "tcga:sample", "gtex:donor"]) == {
        "gtex:sample": "GtexSample",
        "tcga:sample": "TcgaSample",
        "gtex:donor": "Donor",
    }
    # Only the namespace is stripped; the rest of the ID keeps its structure.
    assert export_labels(["study:result.v1"]) == {"study:result.v1": "ResultV1"}
    # Headless export has no ontology root, so no local name is reserved.
    assert export_labels(["x:entity"]) == {"x:entity": "Entity"}
    assert export_labels(["x:query-context"]) == {"x:query-context": "QueryContext"}
    assert export_labels(["x:9lives"]) == {"x:9lives": "Concept9lives"}
    # A collision the namespace cannot resolve falls back to a stable per-ID suffix.
    residual = export_labels(["study:item", "study:ITEM"])
    assert set(residual) == {"study:item", "study:ITEM"}
    assert all(label.startswith("StudyItemH") for label in residual.values())
    assert len(set(residual.values())) == 2


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
            (self.directory / "ResultV1-part000.parquet").write_bytes(b"PAR1")
            return True

        def write_edges(self, rows: object) -> bool:
            return True

        def write_import_call(self) -> None:
            return None

    monkeypatch.setattr("biocypher.BioCypher", ParquetWriter)
    context = RunContext(PIPELINE)
    PIPELINE.run(context)
    with pytest.raises(ValueError, match="declared neo4j-admin-csv contract does not cover"):
        BioCypherWriter("csv").write(context, tmp_path / "mismatch")

    with pytest.raises(ValueError, match="Unsupported export format"):
        BioCypherWriter("avro")


def test_parquet_is_a_supported_declared_format(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    report = build.run_pipeline(PIPELINE, tmp_path / "pq", writer=BioCypherWriter("parquet"))
    assert report["exporter"]["format"] == "neo4j-admin-parquet"

    written = sorted(p.name for p in (tmp_path / "pq/biocypher").iterdir())
    assert written == [
        "ReportedBy-part000.parquet",
        "ResultV1-part000.parquet",
        "Source-part000.parquet",
        "neo4j-admin-import-call.sh",
    ]

    table = pyarrow.parquet.read_table(tmp_path / "pq/biocypher/ResultV1-part000.parquet")
    assert "biotope_provenance_id" in table.column_names
    assert not (tmp_path / "pq/query_context.json").exists()


def test_export_contains_domain_records_schema_descriptions_and_build_report(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    report = build.run_pipeline(PIPELINE, tmp_path / "run")
    assert "query_context" not in report
    for name in ("query_context.json", "topology.json", "ontology.ttl"):
        assert not (tmp_path / "run" / name).exists()
    assert not list((tmp_path / "run/biocypher").glob("BiotopeQueryContext*"))
    schema = yaml.safe_load((tmp_path / "run/schema_config.yaml").read_text())
    finding = schema["ResultV1"]
    assert finding["input_label"] == "study:result.v1"
    assert finding["biotope"]["nullable"] == ["note"]
    assert finding["biotope"]["property_descriptions"]["effect"].startswith("Log2 fold change")
    assert report["graph_objects"] == {"nodes": 2, "edges": 1}


def test_audit_notes_and_counts_reach_the_build_report(tmp_path, monkeypatch):
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

    report = build.run_pipeline(replace(PIPELINE, run=run), tmp_path / "audited")
    assert report["audits"][0]["notes"] == ("One row was withheld pending curation.",)
    assert report["audits"][0]["counts"] == {"read": 2, "kept": 1}
