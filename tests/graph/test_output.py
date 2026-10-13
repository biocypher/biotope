"""Graph export: actual Neo4j and SQLite values, readable labels, the declared format and what exporters refuse."""

import csv
import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, ClassVar, NewType

import pyarrow.parquet
import pytest
import yaml
from synthetic_pipelines import RESULTS_PIPELINE

from biotope.graph import Evidence, Mapping, Pipeline, SourceRecord, Topology, build, output
from biotope.graph.output import ARRAY_DELIMITER, BioCypherWriter, SQLiteWriter, export_labels
from biotope.graph.runtime import RunContext


ItemId = NewType("ItemId", str)
OtherId = NewType("OtherId", str)
ClaimId = NewType("ClaimId", str)


@dataclass(frozen=True)
class ItemRow:
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


@dataclass(frozen=True)
class Claim:
    schema_id: ClassVar[str] = "study:claim"
    id: ClaimId
    biotope_provenance_id: int


def make_item(row: SourceRecord[ItemRow]) -> Iterator[Item]:
    yield Item(ItemId(row.value.identity), row.value.label, row.value.aliases)


def make_other(row: SourceRecord[ItemRow]) -> Iterator[Other]:
    yield Other(OtherId(row.value.identity), None)


def make_claim(row: SourceRecord[ItemRow]) -> Iterator[Claim]:
    yield Claim(ClaimId(row.value.identity), 0)


ITEMS = Mapping(name="items", function=make_item)
OTHERS = Mapping(name="others", function=make_other)
CLAIMS = Mapping(name="claims", function=make_claim)
EXPORT = Pipeline(
    "export",
    Topology((Item,), ()),
    (),
    (ITEMS, OTHERS, CLAIMS),
    lambda context: None,
    scope="CSV representation",
    code_paths=(__file__,),
)
EVIDENCE = (Evidence("items", "v1", "items", "key:1"),)


def header(part: Path) -> list[str]:
    return next(csv.reader([part.with_name(part.name.replace("part000", "header")).read_text()]))


def test_biocypher_labels_and_string_values_round_trip(tmp_path):
    context = RunContext(EXPORT)
    value = ItemRow("item:1", 'Text "quoted", and | delimited', ['alias "quoted"', "with, comma"])
    context.map(ITEMS, SourceRecord(value, EVIDENCE))
    BioCypherWriter().write(context, tmp_path / "readable")
    part = tmp_path / "readable/biocypher/Item-part000.csv"
    with part.open() as stream:
        row = next(csv.DictReader(stream, fieldnames=header(part)))
    assert row["label"] == value.label
    assert row["aliases:string[]"].split(ARRAY_DELIMITER) == value.aliases
    assert row[":LABEL"] == "Item"

    colliding = RunContext(replace(EXPORT, topology=Topology((Item, Other), ())))
    colliding.map(ITEMS, SourceRecord(value, EVIDENCE))
    colliding.map(OTHERS, SourceRecord(replace(value, identity="other:1"), EVIDENCE))
    BioCypherWriter().write(colliding, tmp_path / "colliding")
    schema = yaml.safe_load((tmp_path / "colliding/schema_config.yaml").read_text())
    labels = {item["input_label"]: label for label, item in schema.items()}
    assert len({v for k, v in labels.items() if k.startswith("study:")}) == 2
    other = tmp_path / "colliding/biocypher" / f"{labels['study:ITEM']}-part000.csv"
    with other.open() as stream:
        assert next(csv.DictReader(stream, fieldnames=header(other)))["note"] == ""
    labels_as_written = set()
    for part in (tmp_path / "colliding/biocypher").glob("*-part000.csv"):
        with part.open() as stream:
            labels_as_written.update(next(csv.reader(stream))[-1].split("|"))
    assert labels_as_written == set(labels.values())


def test_a_collected_object_keeps_the_list_its_mapping_changes_later():
    aliases = ["first"]
    context = RunContext(EXPORT)
    context.map(ITEMS, SourceRecord(ItemRow("item:1", "label", aliases), EVIDENCE))
    aliases.append("later")
    assert context.nodes["item:1"].value == Item(ItemId("item:1"), "label", ["first"])


@pytest.mark.parametrize(
    ("mapping", "value", "message"),
    [
        (ITEMS, ItemRow("item:1", "two\nlines", []), r"study:item\.label of item:1 spans several lines"),
        (ITEMS, ItemRow("item:1", "label", [f"a{ARRAY_DELIMITER}b"]), r"study:item\.aliases of item:1 has"),
        (ITEMS, ItemRow('item:"1"', "label", []), r"study:item 'item:\"1\"': an identifier"),
        (CLAIMS, ItemRow("claim:1", "label", []), r"study:claim\.biotope_provenance_id: the exporter reserves"),
    ],
    ids=["multiline", "list_separator", "identifier", "provenance_property"],
)
def test_export_refuses_a_value_it_cannot_represent(tmp_path, unchecked_definitions, mapping, value, message):
    emitted: list[str] = []

    def run(context: RunContext) -> None:
        context.map(mapping, SourceRecord(value, EVIDENCE))
        emitted.append("after")

    pipeline = replace(EXPORT, topology=Topology((Item, Claim), ()), run=run)
    with pytest.raises(build.RunFailed, match=f"{mapping.name}: {message}") as failure:
        build.run_pipeline(pipeline, tmp_path / "run")
    assert emitted == []
    assert failure.value.report["quality"]["blocked_by"] == "execution.failed"

    collected = RunContext(pipeline)
    collected.map(mapping, SourceRecord(value, EVIDENCE))
    with pytest.raises(ValueError, match=message):
        BioCypherWriter().write(collected, tmp_path / "written")


def test_export_labels_drop_the_namespace_and_widen_only_under_collision():
    assert export_labels(["ot:drug", "ot:drug-has-mechanism"]) == {
        "ot:drug": "Drug",
        "ot:drug-has-mechanism": "DrugHasMechanism",
    }
    assert export_labels(["gtex:sample", "tcga:sample", "gtex:donor"]) == {
        "gtex:sample": "GtexSample",
        "tcga:sample": "TcgaSample",
        "gtex:donor": "Donor",
    }
    assert export_labels(["study:result.v1"]) == {"study:result.v1": "ResultV1"}
    assert export_labels(["x:9lives"]) == {"x:9lives": "Concept9lives"}
    residual = export_labels(["study:item", "study:ITEM"])
    assert set(residual) == {"study:item", "study:ITEM"}
    assert all(label.startswith("StudyItemH") for label in residual.values())
    assert len(set(residual.values())) == 2


def test_exporter_version_is_enforced_before_any_payload_is_read(tmp_path, monkeypatch, unchecked_definitions):
    def forbidden(context: RunContext) -> None:
        raise AssertionError("the pipeline ran before the exporter was verified")

    monkeypatch.setattr(output, "SUPPORTED_BIOCYPHER", ((0, 99), (0, 100)))
    with pytest.raises(build.RunFailed) as failure:
        build.run_pipeline(replace(RESULTS_PIPELINE, run=forbidden), tmp_path / "mismatch")
    message = failure.value.report["error"]
    assert ">=0.99,<0.100" in message and "pip install" in message
    assert failure.value.report["quality"]["blocked_by"] == "environment.failed"

    def absent(name: str) -> str:
        raise output.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(output.importlib.metadata, "version", absent)
    with pytest.raises(ValueError, match="not installed"):
        BioCypherWriter().check_environment()


def test_export_refuses_output_the_declared_format_does_not_cover(tmp_path, monkeypatch):
    class ParquetWriter:
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
    context = RunContext(RESULTS_PIPELINE)
    RESULTS_PIPELINE.run(context)
    with pytest.raises(ValueError, match="declared neo4j-admin-csv contract does not cover"):
        BioCypherWriter("csv").write(context, tmp_path / "mismatch")

    with pytest.raises(ValueError, match="Unsupported export format"):
        BioCypherWriter("avro")


def test_parquet_is_a_supported_declared_format(tmp_path, unchecked_definitions):
    report = build.run_pipeline(RESULTS_PIPELINE, tmp_path / "pq", writer=BioCypherWriter("parquet"))
    assert report["exporter"]["format"] == "neo4j-admin-parquet"
    assert sorted(p.name for p in (tmp_path / "pq/biocypher").iterdir()) == [
        "ReportedBy-part000.parquet",
        "ResultV1-part000.parquet",
        "Source-part000.parquet",
        "neo4j-admin-import-call.sh",
    ]
    table = pyarrow.parquet.read_table(tmp_path / "pq/biocypher/ResultV1-part000.parquet")
    assert "biotope_provenance_id" in table.column_names


def test_a_build_exports_schema_descriptions_and_a_relocatable_import_script(tmp_path, unchecked_definitions):
    report = build.run_pipeline(RESULTS_PIPELINE, tmp_path / "run")
    assert report["graph_objects"] == {"nodes": 2, "edges": 1}
    schema = yaml.safe_load((tmp_path / "run/schema_config.yaml").read_text())
    result = schema["ResultV1"]
    assert result["input_label"] == "study:result.v1"
    assert result["biotope"]["nullable"] == ["note"]
    assert result["biotope"]["property_descriptions"]["effect"].startswith("Log2 fold change")
    script = (tmp_path / "run/biocypher/neo4j-admin-import-call.sh").read_text()
    assert str(tmp_path) not in script
    assert "${BIOCYPHER_IMPORT_DIR}" in script
    assert "--read-buffer-size" not in script


def test_a_line_longer_than_the_neo4j_read_buffer_widens_the_import_buffer(tmp_path, unchecked_definitions):
    geometry = "MULTIPOLYGON(((" + "0 0," * 1_100_000 + "0 0)))"
    row = SourceRecord(ItemRow("item:1", geometry, []), EVIDENCE)
    report = build.run_pipeline(replace(EXPORT, run=lambda context: context.map(ITEMS, row)), tmp_path / "run")
    script = (tmp_path / "run/biocypher/neo4j-admin-import-call.sh").read_text()
    assert script.count("--read-buffer-size=8m") == script.count("--delimiter=") == 2
    [finding] = [f for f in report["quality"]["findings"] if f["code"] == "quality.oversized_value"]
    assert finding["subject"] == "study:item.label"
    assert "1 of 1" in finding["message"]


@pytest.mark.parametrize("file_format", ["csv", "parquet"])
def test_an_empty_graph_builds_and_replaces_the_previous_build(tmp_path, file_format, unchecked_definitions):
    output = tmp_path / "build"
    build.run_pipeline(RESULTS_PIPELINE, output, writer=BioCypherWriter(file_format))
    empty = replace(RESULTS_PIPELINE, run=lambda context: None)
    report = build.run_pipeline(empty, output, writer=BioCypherWriter(file_format))
    assert report["state"] == "complete" and report["graph_objects"] == {"nodes": 0, "edges": 0}
    assert sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()) == [
        "biocypher/neo4j-admin-import-call.sh",
        "biocypher_config.yaml",
        "provenance.json",
        "run.json",
        "schema_config.yaml",
    ]


def test_sqlite_keeps_values_neo4j_files_cannot_hold(tmp_path):
    context = RunContext(replace(EXPORT, topology=Topology((Item, Other), ())))
    value = ItemRow("item:1", 'Text "quoted",\tand | delimited\non two lines', ['alias "quoted"', "with, comma; and |"])
    context.map(ITEMS, SourceRecord(value, EVIDENCE))
    context.map(OTHERS, SourceRecord(replace(value, identity="other:1"), EVIDENCE))
    files = SQLiteWriter().write(context, tmp_path / "db")
    assert files == ["graph.sqlite", "provenance.json", "schema_config.yaml"]
    schema = yaml.safe_load((tmp_path / "db/schema_config.yaml").read_text())
    labels = {item["input_label"]: label for label, item in schema.items()}
    with sqlite3.connect(tmp_path / "db/graph.sqlite") as connection:
        item = connection.execute(f'SELECT id, label, aliases, biotope_provenance_id FROM "{labels["study:item"]}"')
        identity, label, aliases, provenance = item.fetchone()
        note = connection.execute(f'SELECT note FROM "{labels["study:ITEM"]}"').fetchone()
    assert (identity, label, json.loads(aliases)) == ("item:1", value.label, value.aliases)
    assert note == (None,)
    catalog = json.loads((tmp_path / "db/provenance.json").read_text())
    assert catalog["records"][provenance]["mappings"] == ["items"]


def test_a_sqlite_build_types_columns_and_references_edge_endpoints(tmp_path, unchecked_definitions):
    report = build.run_pipeline(RESULTS_PIPELINE, tmp_path / "run", writer=SQLiteWriter())
    assert report["exporter"]["format"] == "sqlite"
    assert sorted(p.name for p in (tmp_path / "run").iterdir()) == [
        "graph.sqlite",
        "provenance.json",
        "run.json",
        "schema_config.yaml",
    ]
    with sqlite3.connect(tmp_path / "run/graph.sqlite") as connection:
        columns = {row[1]: row[2] for row in connection.execute('PRAGMA table_info("ResultV1")')}
        references = {row[3]: row[2] for row in connection.execute('PRAGMA foreign_key_list("ReportedBy")')}
        counts = [connection.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in ("ResultV1", "ReportedBy")]
    assert columns["id"] == "TEXT" and columns["effect"] == "REAL" and columns["biotope_provenance_id"] == "INTEGER"
    assert references == {"source": "ResultV1", "target": "Source"}
    assert counts == [1, 1]


def test_sqlite_refuses_a_property_named_like_a_column_it_writes(tmp_path):
    context = RunContext(replace(EXPORT, topology=Topology((Item, Claim), ())))
    context.map(CLAIMS, SourceRecord(ItemRow("claim:1", "label", []), EVIDENCE))
    with pytest.raises(ValueError, match=r"study:claim\.biotope_provenance_id: the exporter reserves"):
        SQLiteWriter().write(context, tmp_path / "db")
