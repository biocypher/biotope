"""Typed topology and runtime integrity at the graph boundary."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar, NewType, cast

import pytest

from biotope.graph import Evidence, Mapping, MappingEntry, Pipeline, SourceRecord, Topology
from biotope.graph.runtime import RunContext


PersonId = NewType("PersonId", str)
SampleId = NewType("SampleId", str)


@dataclass(frozen=True)
class PersonRow:
    """A synthetic row of the people record set."""

    person_id: str
    name: str


@dataclass(frozen=True)
class SampleRow:
    """A synthetic row of the samples record set."""

    person_id: str
    sample_id: str


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


TOPOLOGY = Topology(nodes=(Person, Sample), edges=(FromPerson,))


def make_person(row: SourceRecord[PersonRow]) -> Iterator[Person]:
    """Produce one person node from one source row."""
    yield Person(PersonId(f"study:person:{row.value.person_id}"), row.value.name)


def bad_property(row: SourceRecord[PersonRow]) -> Iterator[Person]:
    """Ignore the declared property type; the runtime must still refuse the value."""
    yield Person(PersonId(f"study:person:{row.value.person_id}"), cast(str, 5))


def bad_identifier(row: SourceRecord[PersonRow]) -> Iterator[Person]:
    """Mint an identifier without a namespace."""
    yield Person(PersonId(row.value.person_id), row.value.name)


def undeclared(row: SourceRecord[PersonRow]) -> Iterator[Person]:
    """Yield a class the return annotation never declared."""
    yield cast(Person, Sample(SampleId(f"study:sample:{row.value.person_id}")))


def join(person: SourceRecord[PersonRow], sample: SourceRecord[SampleRow]) -> Iterator[FromPerson]:
    """Relate a sample to the person it came from."""
    yield FromPerson(
        SampleId(f"study:sample:{sample.value.sample_id}"), PersonId(f"study:person:{person.value.person_id}")
    )


def reserved_names(*, mapping: SourceRecord[PersonRow], self: SourceRecord[SampleRow]) -> Iterator[FromPerson]:
    """Use the composition helpers' own parameter names as mapping input names."""
    yield FromPerson(
        SampleId(f"study:sample:{self.value.sample_id}"), PersonId(f"study:person:{mapping.value.person_id}")
    )


PEOPLE = Mapping(name="people", function=make_person)
BAD_PROPERTY = Mapping(name="bad-property", function=bad_property)
BAD_IDENTIFIER = Mapping(name="bad-identifier", function=bad_identifier)
UNDECLARED = Mapping(name="undeclared", function=undeclared)
JOIN = Mapping(name="join", function=join)
RESERVED = Mapping(name="reserved", function=reserved_names)


def context(*mappings: MappingEntry, topology: Topology = TOPOLOGY) -> RunContext:
    """A run context over the selected registrations and nothing else."""
    return RunContext(
        Pipeline("test", topology, (), mappings, lambda ctx: None, scope="unit example", code_paths=(__file__,))
    )


def person(identity: str, name: str, artifact: str = "people.csv", version: str = "v1") -> SourceRecord[PersonRow]:
    """One evidence-bearing people row."""
    return SourceRecord(PersonRow(identity, name), (Evidence(artifact, version, "people", f"row:{identity}"),))


def test_topology_semantics_and_value_integrity():
    before = TOPOLOGY.describe()
    old_module = Person.__module__
    try:
        Person.__module__ = "moved.topology.person"
        assert TOPOLOGY.describe() == before
    finally:
        Person.__module__ = old_module
    assert before["study:from-person"]["source"] == "study:sample"
    with pytest.raises(ValueError, match="duplicate"):
        Topology(nodes=(Person, Person), edges=()).describe()

    run = context(PEOPLE, BAD_PROPERTY, BAD_IDENTIFIER, UNDECLARED)
    run.map(PEOPLE, person("1", "Ada"))
    run.map(PEOPLE, person("1", "Ada", artifact="other.csv", version="v2"))
    assert len(run.nodes) == 1
    assert len(next(iter(run.nodes.values())).evidence) == 2
    with pytest.raises(ValueError, match="Conflicting"):
        run.map(PEOPLE, person("1", "Changed"))
    with pytest.raises(ValueError, match="name"):
        run.map(BAD_PROPERTY, person("2", "Ada"))
    with pytest.raises(ValueError, match="identifier"):
        run.map(BAD_IDENTIFIER, person("unscoped", "Ada"))
    with pytest.raises(ValueError, match="undeclared output Sample"):
        run.map(UNDECLARED, person("3", "Ada"))
    with pytest.raises(ValueError, match="evidence"):
        run.map(PEOPLE, SourceRecord(PersonRow("4", "Ada"), ()))

    edges = context(JOIN)
    edges.map(JOIN, person("1", "Ada"), SourceRecord(SampleRow("1", "s1"), (Evidence("s.csv", "v1", "samples", "1"),)))
    with pytest.raises(ValueError, match="unresolved"):
        edges.validate_references()


def test_mapping_checks_its_call_and_keeps_combined_evidence():
    run = context(JOIN)
    a, b = Evidence("a", "v1", "people", "1"), Evidence("b", "v1", "samples", "2")
    ada, sample = SourceRecord(PersonRow("1", "Ada"), (a,)), SourceRecord(SampleRow("1", "s2"), (b,))
    outputs = list(run.apply(JOIN, ada, sample))
    assert outputs[0].evidence == (a, b)
    with pytest.raises(ValueError, match="input 'person'"):
        list(run.apply(JOIN, cast(SourceRecord[PersonRow], sample), sample))
    with pytest.raises(ValueError, match="missing a required argument"):
        list(run.apply(JOIN, ada))  # pyright: ignore[reportCallIssue]
    with pytest.raises(ValueError, match="expected a SourceRecord"):
        list(run.apply(JOIN, cast(SourceRecord[PersonRow], ada.value), sample))
    with pytest.raises(ValueError, match="Unregistered mapping"):
        list(context(PEOPLE).apply(JOIN, ada, sample))


def test_every_input_needs_its_own_evidence():
    run = context(JOIN)
    ada = SourceRecord(PersonRow("1", "Ada"), (Evidence("a", "v1", "people", "1"),))
    anonymous = SourceRecord(SampleRow("1", "s2"), ())
    called: list[str] = []

    def watched(person: SourceRecord[PersonRow], sample: SourceRecord[SampleRow]) -> Iterator[FromPerson]:
        called.append("ran")
        yield from join(person, sample)

    watching = context(Mapping(name="join", function=watched))
    # One contributor-bearing input must not cover for an input that has none.
    with pytest.raises(ValueError, match="input 'sample': Every graph/source record needs source evidence"):
        list(watching.apply(Mapping(name="join", function=watched), ada, anonymous))
    assert called == []
    blank = SourceRecord(SampleRow("1", "s2"), (Evidence("b", "v1", "samples", "   "),))
    with pytest.raises(ValueError, match="input 'sample'"):
        list(run.apply(JOIN, ada, blank))
    # Valid multi-input provenance is untouched.
    sample = SourceRecord(SampleRow("1", "s2"), (Evidence("b", "v1", "samples", "2"),))
    assert len(next(iter(run.apply(JOIN, ada, sample))).evidence) == 2


def test_mappings_may_use_the_composition_helpers_own_parameter_names():
    run = context(RESERVED)
    ada = SourceRecord(PersonRow("1", "Ada"), (Evidence("a", "v1", "people", "1"),))
    sample = SourceRecord(SampleRow("1", "s2"), (Evidence("b", "v1", "samples", "2"),))
    outputs = list(run.apply(RESERVED, mapping=ada, self=sample))
    assert outputs[0].value == FromPerson(SampleId("study:sample:s2"), PersonId("study:person:1"))
    run.map(RESERVED, mapping=ada, self=sample)
    assert len(run.edges) == 1


def test_exclusions_aggregate_counts_and_bound_evidence():
    run = RunContext(
        Pipeline(
            "excluded",
            Topology((), ()),
            (),
            (),
            lambda ctx: None,
            scope="declared exclusions",
            code_paths=(__file__,),
            policies={"unmatched": "No join partner", "filtered": "Out of scope"},
        )
    )
    for index in range(20):
        run.exclude("unmatched", (Evidence("rows", "v1", "rows", f"row:{index}"),))
    run.exclude("unmatched", (Evidence("rows", "v2", "rows", "keys:20-24"),), count=5)
    run.exclude("filtered", (Evidence("rows", "v2", "rows", "row:25"),))
    assert len(run.findings) == 2
    finding = next(item for item in run.findings if item["policy"] == "unmatched")
    assert finding["count"] == 25
    assert len(finding["evidence_sample"]) == 10
    assert finding["evidence_truncated"] is True
    assert run.source_versions == {("rows", "v1"), ("rows", "v2")}
