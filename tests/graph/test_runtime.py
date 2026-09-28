"""Typed topology and runtime integrity at the graph boundary."""

import math
from collections.abc import Iterator
from dataclasses import dataclass, replace
from itertools import islice
from pathlib import Path
from typing import ClassVar, NewType, cast

import pytest
from synthetic_pipelines import RESULTS, RESULTS_PIPELINE, RecordingWriter, ResultRow, emit_results, result_row

from biotope.graph import Evidence, Mapping, MappingEntry, Pipeline, SourceContract, SourceRecord, Topology, build
from biotope.graph.runtime import RunContext


PersonId = NewType("PersonId", str)
SampleId = NewType("SampleId", str)


@dataclass(frozen=True)
class PersonRow:
    person_id: str
    name: str


@dataclass(frozen=True)
class SampleRow:
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
    yield Person(PersonId(f"study:person:{row.value.person_id}"), row.value.name)


def mistyped_property(row: SourceRecord[PersonRow]) -> Iterator[Person]:
    yield Person(PersonId(f"study:person:{row.value.person_id}"), cast(str, 5))


def unnamespaced_identifier(row: SourceRecord[PersonRow]) -> Iterator[Person]:
    yield Person(PersonId(row.value.person_id), row.value.name)


def undeclared_output(row: SourceRecord[PersonRow]) -> Iterator[Person]:
    yield cast(Person, Sample(SampleId(f"study:sample:{row.value.person_id}")))


def join(person: SourceRecord[PersonRow], sample: SourceRecord[SampleRow]) -> Iterator[FromPerson]:
    yield FromPerson(
        SampleId(f"study:sample:{sample.value.sample_id}"), PersonId(f"study:person:{person.value.person_id}")
    )


def reserved_names(*, mapping: SourceRecord[PersonRow], self: SourceRecord[SampleRow]) -> Iterator[FromPerson]:
    yield FromPerson(
        SampleId(f"study:sample:{self.value.sample_id}"), PersonId(f"study:person:{mapping.value.person_id}")
    )


PEOPLE = Mapping(name="people", function=make_person)
MISTYPED_PROPERTY = Mapping(name="mistyped-property", function=mistyped_property)
UNNAMESPACED_IDENTIFIER = Mapping(name="unnamespaced-identifier", function=unnamespaced_identifier)
UNDECLARED_OUTPUT = Mapping(name="undeclared-output", function=undeclared_output)
JOIN = Mapping(name="join", function=join)
RESERVED = Mapping(name="reserved", function=reserved_names)


@dataclass(frozen=True)
class Grouped:
    symbols: tuple[str, ...]
    pair: tuple[str, int]
    samples: tuple[SampleRow, ...] = ()


def pass_through(row: SourceRecord[Grouped]) -> Iterator[Grouped]:
    yield row.value


PASS_THROUGH = Mapping(name="pass-through", function=pass_through)


def context(*mappings: MappingEntry) -> RunContext:
    return RunContext(
        Pipeline("test", TOPOLOGY, (), mappings, lambda ctx: None, scope="unit example", code_paths=(__file__,))
    )


def person(identity: str, name: str, artifact: str = "people.csv", version: str = "v1") -> SourceRecord[PersonRow]:
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

    run = context(PEOPLE, MISTYPED_PROPERTY, UNNAMESPACED_IDENTIFIER, UNDECLARED_OUTPUT)
    run.map(PEOPLE, person("1", "Ada"))
    run.map(PEOPLE, person("1", "Ada", artifact="other.csv", version="v2"))
    assert len(run.nodes) == 1
    assert len(next(iter(run.nodes.values())).evidence) == 2
    with pytest.raises(ValueError, match="Conflicting"):
        run.map(PEOPLE, person("1", "Changed"))
    with pytest.raises(ValueError, match="name"):
        run.map(MISTYPED_PROPERTY, person("2", "Ada"))
    with pytest.raises(ValueError, match="identifier"):
        run.map(UNNAMESPACED_IDENTIFIER, person("unscoped", "Ada"))
    with pytest.raises(ValueError, match="undeclared output Sample"):
        run.map(UNDECLARED_OUTPUT, person("3", "Ada"))
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
    with pytest.raises(ValueError, match="input 'sample': Every graph/source record needs source evidence"):
        list(watching.apply(Mapping(name="join", function=watched), ada, anonymous))
    assert called == []
    blank = SourceRecord(SampleRow("1", "s2"), (Evidence("b", "v1", "samples", "   "),))
    with pytest.raises(ValueError, match="input 'sample'"):
        list(run.apply(JOIN, ada, blank))
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


def test_intermediates_may_hold_tuples_whose_items_are_checked():
    run = context(PASS_THROUGH)
    evidence = (Evidence("groups.csv", "v1", "groups", "1"),)
    valid = Grouped(("TSPAN6",), ("x", 1), (SampleRow("1", "s1"),))
    assert [output.value for output in run.apply(PASS_THROUGH, SourceRecord(valid, evidence))] == [valid]
    invalid = {
        r"\.symbols\[1\]: expected": Grouped(("A", cast(str, 2)), ("x", 1)),
        r"\.pair\[1\]: expected": Grouped(("A",), ("x", cast(int, "1"))),
        r"\.pair: expected .*, got 1 items": Grouped(("A",), cast(tuple[str, int], ("x",))),
        r"\.symbols: expected .*, got list": Grouped(cast(tuple[str, ...], ["A"]), ("x", 1)),
    }
    for message, value in invalid.items():
        with pytest.raises(ValueError, match=message):
            list(run.apply(PASS_THROUGH, SourceRecord(value, evidence)))


@dataclass(frozen=True)
class Label:
    text: str


@dataclass(frozen=True)
class Measurement:
    __record_set__: ClassVar[str] = "measurements"
    score: float
    tags: list[str]
    rank: int | None
    label: Label


def measured_person(row: SourceRecord[Measurement]) -> Iterator[Person]:
    yield Person(PersonId("study:person:1"), row.value.label.text)


def test_load_and_map_refuse_values_outside_their_declarations_by_path():
    source = SourceContract("measurements", Path("measurements.jsonld"), Path(__file__), (Measurement,))
    measured = Mapping(name="measured", function=measured_person)
    run = RunContext(Pipeline("test", TOPOLOGY, (source,), (measured,), lambda ctx: None, scope="unit", code_paths=()))
    evidence = (Evidence("measurements.csv", "v1", "measurements", "row:1"),)
    valid = SourceRecord(Measurement(1.5, ["a", "b"], None, Label("Ada")), evidence)
    assert list(run.load(source, lambda config: iter((valid,)), None)) == [valid]
    run.map(measured, valid)
    invalid = {
        r"\.score: non-finite": replace(valid.value, score=math.nan),
        r"\.tags\[1\]: expected": replace(valid.value, tags=["a", cast(str, 2)]),
        r"\.rank: 'high' does not satisfy": replace(valid.value, rank=cast(int, "high")),
        r"\.label\.text: expected": replace(valid.value, label=Label(cast(str, 3))),
    }
    for message, value in invalid.items():
        record = SourceRecord(value, evidence)
        with pytest.raises(ValueError, match=message):
            list(run.load(source, lambda config: iter((record,)), None))
        with pytest.raises(ValueError, match=message):
            run.map(measured, record)
    assert len(run.nodes) == 1


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


def test_structural_checks_alone_cannot_see_a_dropped_record(tmp_path, unchecked_definitions):
    """Only an expectation derived independently from the source can notice a silently dropped record."""
    eligible = ("a", "b")
    dropped = replace(RESULTS_PIPELINE, run=lambda context: emit_results(context, eligible[:1]))
    writer = RecordingWriter()
    report = build.run_pipeline(dropped, tmp_path / "build", writer=writer)
    assert writer.calls == ["environment", "export"] and report["state"] == "complete"
    assert report["graph_objects"] == {"nodes": 2, "edges": 1}
    assert report["findings"] == []
    assert report["quality"]["state"] == "complete" and report["quality"]["findings"] == []


def test_audits_record_stage_accounting_without_imposing_arithmetic(tmp_path, unchecked_definitions):
    reads = {"reads": 4, "distinct_keys": 2, "results": 2}
    notes = ("Unresolved keys limit the join; the results themselves are retained.",)

    def run(context: RunContext) -> None:
        emit_results(context, ("a", "b"))
        context.record_audit(
            "read:results",
            inputs="one row per key, read once for identity and once for values",
            outputs="one Result per distinct key",
            selection="Keep every eligible row.",
            counts=reads,
            evidence=(Evidence("rows", "v1", "results", "a"),),
        )
        context.record_audit(
            "join:annotations",
            inputs="one Result per key",
            outputs="one annotation edge per resolved key",
            selection="Join only where the reference table supplies an identifier.",
            counts={"results": 2, "resolved": 0, "unresolvable": 2},
            notes=notes,
        )

    report = build.run_pipeline(replace(RESULTS_PIPELINE, run=run), tmp_path / "audit", writer=RecordingWriter())
    read, join = report["audits"]
    assert read["stage"] == "read:results" and read["counts"] == reads
    assert read["evidence_sample"][0]["location"] == "a"
    assert join["stage"] == "join:annotations" and join["notes"] == notes

    context = RunContext(RESULTS_PIPELINE)
    context.record_audit("s", inputs="i", outputs="o", selection="all", counts={})
    with pytest.raises(ValueError, match="already recorded"):
        context.record_audit("s", inputs="i", outputs="o", selection="all", counts={})
    with pytest.raises(ValueError, match="non-empty selection"):
        context.record_audit("t", inputs="i", outputs="o", selection=" ", counts={})
    with pytest.raises(ValueError, match="non-negative integer"):
        context.record_audit("u", inputs="i", outputs="o", selection="all", counts={"n": -1})


def test_a_build_fails_unless_every_selected_loader_finished(tmp_path, unchecked_definitions):
    rows = SourceContract("rows", Path("rows.jsonld"), Path(__file__), (ResultRow,))
    empty = SourceContract("empty", Path("empty.jsonld"), Path(__file__), (ResultRow,))
    selected = replace(RESULTS_PIPELINE, sources=(rows, empty), source_inventory=(rows, empty))

    def read(context: RunContext, count: int | None) -> None:
        list(context.load(empty, lambda config: iter(()), None))
        records = context.load(rows, lambda config: iter((result_row("a"), result_row("b"))), None)
        for record in islice(records, count):
            context.map(RESULTS, record)

    def attempt(count: int | None) -> dict[str, object]:
        pipeline = replace(selected, run=lambda context: read(context, count))
        return build.run_pipeline(pipeline, tmp_path / "build", writer=RecordingWriter())

    assert attempt(None)["loaded_records"] == {"empty": 0, "rows": 2}
    with pytest.raises(build.RunFailed, match=r"did not finish: \['rows'\]") as failure:
        attempt(1)
    assert failure.value.report["loaded_records"] == {"empty": 0, "rows": 1}
