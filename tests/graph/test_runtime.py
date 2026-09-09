"""Typed topology and runtime integrity at the graph boundary."""

from dataclasses import dataclass
from typing import ClassVar, NewType

import pytest

from biotope.graph import Evidence, Mapping, Pipeline, SourceRecord, Topology
from biotope.graph.runtime import RunContext


PersonId = NewType("PersonId", str)
SampleId = NewType("SampleId", str)


@dataclass(frozen=True)
class Person:
    schema_id: ClassVar[str] = "study:person"
    id: PersonId
    name: str


@dataclass(frozen=True)
class Sample:
    schema_id: ClassVar[str] = "study:sample"
    id: SampleId


@dataclass(frozen=True)
class FromPerson:
    schema_id: ClassVar[str] = "study:from-person"
    source: SampleId
    target: PersonId


def test_topology_semantics_and_value_integrity(tmp_path):
    topology = Topology(nodes=(Person, Sample), edges=(FromPerson,))
    before = topology.describe()
    old_module = Person.__module__
    try:
        Person.__module__ = "moved.topology.person"
        assert topology.describe() == before
    finally:
        Person.__module__ = old_module
    assert before["study:from-person"]["source"] == "study:sample"
    with pytest.raises(ValueError, match="duplicate"):
        Topology(nodes=(Person, Person), edges=()).describe()

    def transform(row: Person) -> tuple[Person]:
        return (row,)

    mapping = Mapping("people", transform, (Person,), (Person,))
    pipeline = Pipeline(
        "test", topology, (), (mapping,), lambda ctx: None, scope="unit example", code_paths=(__file__,)
    )
    context = RunContext(pipeline)
    evidence = (Evidence("people.csv", "v1", "people", "row:1"),)
    context.emit(Person(PersonId("study:person:1"), "Ada"), evidence, mapping="people")
    context.emit(
        Person(PersonId("study:person:1"), "Ada"), (Evidence("other.csv", "v2", "people", "row:8"),), mapping="people"
    )
    assert len(context.nodes) == 1
    assert len(next(iter(context.nodes.values())).evidence) == 2
    with pytest.raises(ValueError, match="conflict"):
        context.emit(Person(PersonId("study:person:1"), "Changed"), evidence, mapping="people")
    with pytest.raises(ValueError, match="name"):
        context.emit(Person(PersonId("study:person:2"), 5), evidence, mapping="people")
    with pytest.raises(ValueError, match="identifier"):
        context.emit(Person(PersonId("unscoped"), "Ada"), evidence, mapping="people")
    with pytest.raises(ValueError, match="evidence"):
        context.emit(Person(PersonId("study:person:3"), "Ada"), (), mapping="people")
    edge_mapping = Mapping("edges", lambda: (), (), (FromPerson,))
    context = RunContext(
        Pipeline("edges", topology, (), (edge_mapping,), lambda ctx: None, scope="unit", code_paths=(__file__,))
    )
    context.emit(FromPerson(SampleId("study:sample:1"), PersonId("study:person:1")), evidence, mapping="edges")
    with pytest.raises(ValueError, match="unresolved"):
        context.validate_references()


def test_mapping_keeps_combined_evidence_and_checks_inputs():
    def join(left: Person, right: Sample) -> tuple[FromPerson]:
        return (FromPerson(right.id, left.id),)

    mapping = Mapping("join", join, (Person, Sample), (FromPerson,))
    pipeline = Pipeline(
        "joined",
        Topology((Person, Sample), (FromPerson,)),
        (),
        (mapping,),
        lambda ctx: None,
        scope="unit",
        code_paths=(__file__,),
    )
    context = RunContext(pipeline)
    a, b = Evidence("a", "v1", "people", "1"), Evidence("b", "v1", "samples", "2")
    outputs = list(
        context.apply(
            mapping, SourceRecord(Person(PersonId("p:1"), "Ada"), (a,)), SourceRecord(Sample(SampleId("s:2")), (b,))
        )
    )
    assert outputs[0].evidence == (a, b)
    with pytest.raises(ValueError, match="input"):
        list(
            context.apply(
                mapping, SourceRecord(Sample(SampleId("s:2")), (b,)), SourceRecord(Sample(SampleId("s:2")), (b,))
            )
        )


def test_exclusions_aggregate_counts_and_bound_evidence():
    pipeline = Pipeline(
        "excluded",
        Topology((), ()),
        (),
        (),
        lambda ctx: None,
        scope="declared exclusions",
        code_paths=(__file__,),
        policies={"unmatched": "No join partner", "filtered": "Out of scope"},
    )
    context = RunContext(pipeline)
    for index in range(20):
        context.exclude("unmatched", (Evidence("rows", "v1", "rows", f"row:{index}"),))
    context.exclude("unmatched", (Evidence("rows", "v2", "rows", "keys:20-24"),), count=5)
    context.exclude("filtered", (Evidence("rows", "v2", "rows", "row:25"),))
    assert len(context.findings) == 2
    finding = next(item for item in context.findings if item["policy"] == "unmatched")
    assert finding["count"] == 25
    assert len(finding["evidence_sample"]) == 10
    assert finding["evidence_truncated"] is True
    assert context.source_versions == {("rows", "v1"), ("rows", "v2")}
