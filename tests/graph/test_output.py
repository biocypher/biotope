"""Actual Neo4j CSV values, readable labels and collision disambiguation."""

import csv
import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import ClassVar, NewType

import pytest

from biotope.graph import Evidence, Mapping, Pipeline, SourceRecord, Topology
from biotope.graph.context import build_query_context
from biotope.graph.output import ARRAY_DELIMITER, BioCypherWriter, export_labels
from biotope.graph.runtime import RunContext


def context_document(context: RunContext) -> dict:
    """The document a real build hands the writer, derived from the same declarations."""
    return build_query_context(
        context.pipeline,
        schema=context.schema,
        descriptions=context.pipeline.topology.descriptions(),
        labels=export_labels(context.schema),
        report={},
    )


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
    BioCypherWriter().write(context, tmp_path / "readable", query_context=context_document(context))
    output = tmp_path / "readable/biocypher/StudyItem-part000.csv"
    header = next(csv.reader([(output.parent / "StudyItem-header.csv").read_text()]))
    with output.open() as stream:
        row = next(csv.DictReader(stream, fieldnames=header))
    assert row["label"] == value.label
    assert row["aliases:string[]"].split(ARRAY_DELIMITER) == value.aliases
    # labels_order "Leaves" keeps the concept label and drops the synthetic ontology root.
    assert row[":LABEL"] == "StudyItem"
    # A literal array separator cannot be represented unambiguously; reject it.
    invalid = RunContext(pipeline)
    invalid.map(ITEMS, SourceRecord(replace(value, aliases=[f"a{ARRAY_DELIMITER}b"]), evidence))
    with pytest.raises(ValueError, match="string-list separator"):
        BioCypherWriter().write(invalid, tmp_path / "invalid", query_context=context_document(invalid))

    colliding = RunContext(replace(pipeline, topology=Topology((Item, Other), ())))
    colliding.map(ITEMS, SourceRecord(value, evidence))
    colliding.map(OTHERS, SourceRecord(replace(value, identity="other:1"), evidence))
    BioCypherWriter().write(colliding, tmp_path / "colliding", query_context=context_document(colliding))
    topology = json.loads((tmp_path / "colliding/topology.json").read_text())
    labels = topology["export_labels"]
    assert len({v for k, v in labels.items() if k.startswith("study:")}) == 2
    # The reserved metadata label is exported alongside, and never taken by a project concept.
    assert labels["biotope:query-context"] == "BiotopeQueryContext"
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
