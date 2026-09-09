"""Actual Neo4j CSV values, readable labels and collision disambiguation."""

import csv
import json
from dataclasses import dataclass, replace
from typing import ClassVar, NewType

import pytest

from biotope.graph import Evidence, Mapping, Pipeline, Topology
from biotope.graph.output import BioCypherWriter
from biotope.graph.runtime import RunContext


ItemId = NewType("ItemId", str)
OtherId = NewType("OtherId", str)


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


def test_biocypher_labels_and_string_values_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mapping = Mapping("items", lambda: (), (), (Item, Other))
    pipeline = Pipeline(
        "export",
        Topology((Item,), ()),
        (),
        (mapping,),
        lambda ctx: None,
        scope="CSV representation",
        code_paths=(__file__,),
    )
    context = RunContext(pipeline)
    evidence = (Evidence("items", "v1", "items", "key:1"),)
    value = Item(ItemId("item:1"), 'Text "quoted", and | delimited', ['alias "quoted"', "with, comma"])
    context.emit(value, evidence, mapping="items")
    BioCypherWriter().write(context, tmp_path / "readable")
    output = tmp_path / "readable/biocypher/StudyItem-part000.csv"
    header = next(csv.reader([(output.parent / "StudyItem-header.csv").read_text()]))
    with output.open() as stream:
        row = next(csv.DictReader(stream, fieldnames=header))
    assert row["label"] == value.label
    assert row["aliases:string[]"].split("|") == value.aliases
    assert set(row[":LABEL"].split("|")) == {"StudyItem", "Entity"}
    # A literal array separator cannot be represented unambiguously; reject it.
    invalid = RunContext(pipeline)
    invalid.emit(replace(value, aliases=["a|b"]), evidence, mapping="items")
    with pytest.raises(ValueError, match="string-list separator"):
        BioCypherWriter().write(invalid, tmp_path / "invalid")

    colliding = RunContext(replace(pipeline, topology=Topology((Item, Other), ())))
    colliding.emit(value, evidence, mapping="items")
    colliding.emit(Other(OtherId("other:1")), evidence, mapping="items")
    BioCypherWriter().write(colliding, tmp_path / "colliding")
    topology = json.loads((tmp_path / "colliding/topology.json").read_text())
    labels = topology["export_labels"]
    assert len(set(labels.values())) == 2
    # Both labels must survive the writer's own PascalCase conversion.
    actual = set()
    for path in (tmp_path / "colliding/biocypher").glob("*-part000.csv"):
        with path.open() as stream:
            actual.update(next(csv.reader(stream))[-1].split("|"))
    assert actual - {"Entity"} == set(labels.values())
