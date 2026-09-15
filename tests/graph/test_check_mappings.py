"""One signature is the whole contract: what it derives and how it fails."""

from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass, replace
from typing import Any, ClassVar, NewType, TypeVar

import pytest

from biotope.graph import Mapping, MappingEntry, Pipeline, SourceRecord, Topology
from biotope.graph.check import check_pipeline
from biotope.graph.reports import CheckFailed
from biotope.graph.signatures import SignatureError, contract


ThingId = NewType("ThingId", str)
Unsolved = TypeVar("Unsolved")
OtherId = NewType("OtherId", str)


@dataclass(frozen=True)
class Row:
    """A synthetic source row."""

    key: str


@dataclass(frozen=True)
class Alternate:
    """A second source row accepted by the same parameter."""

    key: str


@dataclass(frozen=True)
class Value:
    """An intermediate that declares no graph identity."""

    key: str


@dataclass(frozen=True)
class Thing:
    """A registered graph node."""

    schema_id: ClassVar[str] = "check:thing"
    id: ThingId


@dataclass(frozen=True)
class Stray:
    """A graph node deliberately left out of the topology."""

    schema_id: ClassVar[str] = "check:stray"
    id: OtherId


TOPOLOGY = Topology(nodes=(Thing,), edges=())


def as_iterable(row: SourceRecord[Row]) -> Iterable[Value]: ...
def as_iterator(row: SourceRecord[Row]) -> Iterator[Value]: ...
def as_generator(row: SourceRecord[Row]) -> Generator[Value, None, None]: ...
def as_list(row: SourceRecord[Row]) -> list[Value]: ...
def as_repeated_tuple(row: SourceRecord[Row]) -> tuple[Value, ...]: ...
def as_fixed_tuple(row: SourceRecord[Row]) -> tuple[Value, Thing]: ...
def as_union(row: SourceRecord[Row]) -> Iterator[Value | Thing]: ...
def union_input(row: SourceRecord[Row | Alternate]) -> Iterator[Value]: ...
def split_union_input(row: SourceRecord[Row] | SourceRecord[Alternate]) -> Iterator[Value]: ...
def keyword_only(row: SourceRecord[Row], *, other: SourceRecord[Alternate]) -> Iterator[Value]: ...


SHAPES = {
    as_iterable: ((("row", (Row,)),), (Value,)),
    as_iterator: ((("row", (Row,)),), (Value,)),
    as_generator: ((("row", (Row,)),), (Value,)),
    as_list: ((("row", (Row,)),), (Value,)),
    as_repeated_tuple: ((("row", (Row,)),), (Value,)),
    as_fixed_tuple: ((("row", (Row,)),), (Value, Thing)),
    as_union: ((("row", (Row,)),), (Value, Thing)),
    union_input: ((("row", (Row, Alternate)),), (Value,)),
    split_union_input: ((("row", (Row, Alternate)),), (Value,)),
    keyword_only: ((("row", (Row,)), ("other", (Alternate,))), (Value,)),
}


def test_supported_shapes_derive_their_contract():
    for function, (parameters, outputs) in SHAPES.items():
        derived = contract(Mapping(name=function.__name__, function=function))
        assert tuple((p.name, p.accepts) for p in derived.parameters) == parameters, function.__name__
        assert derived.outputs == outputs, function.__name__
        assert derived.path is not None and derived.line is not None


def untyped(row) -> Iterator[Value]: ...
def variadic(*rows: SourceRecord[Row]) -> Iterator[Value]: ...
def defaulted(row: SourceRecord[Row], scale: float = 1.0) -> Iterator[Value]: ...
def unwrapped(row: Row) -> Iterator[Value]: ...
def anything(row: SourceRecord[Any]) -> Iterator[Value]: ...
def bare_return(row: SourceRecord[Row]) -> Iterator: ...
def unparameterised(row: SourceRecord[Row]) -> list: ...
def not_iterable(row: SourceRecord[Row]) -> Value: ...
def opaque_output(row: SourceRecord[Row]) -> Iterator[object]: ...
def no_inputs() -> Iterator[Value]: ...
def unannotated_return(row: SourceRecord[Row]): ...
def unregistered_output(row: SourceRecord[Row]) -> Iterator[Stray]: ...
def unresolved(row: "SourceRecord[Absent]") -> Iterator[Value]: ...  # noqa: F821
def type_variable(row: SourceRecord[Unsolved]) -> Iterator[Value]: ...


REJECTED = {
    untyped: "parameter 'row': annotate it as SourceRecord",
    variadic: "parameter 'rows': variadic",
    defaulted: "parameter 'scale': a registered mapping takes no defaulted parameters",
    unwrapped: "parameter 'row': annotate mapping inputs as SourceRecord[...]",
    anything: "parameter 'row': expected a concrete dataclass or a finite union of them, got Any",
    bare_return: "return: annotate the return as a parameterized Iterable",
    unparameterised: "return: annotate the return as a parameterized Iterable",
    not_iterable: "return: annotate the return as a parameterized Iterable",
    opaque_output: "return: expected a concrete dataclass or a finite union of them, got object",
    no_inputs: "parameters: a mapping needs at least one evidence-bearing input",
    unannotated_return: "return: annotate the iterable of dataclasses the mapping produces",
    unregistered_output: "return: register these graph outputs in the topology: Stray",
    unresolved: "annotations: could not be resolved",
    type_variable: "parameter 'row': expected a concrete dataclass or a finite union of them",
}


def test_invalid_signatures_are_reported_together_without_running_project_code():
    executed: list[str] = []

    def run(context):
        executed.append("run")

    pipeline = Pipeline(
        "check:signatures",
        TOPOLOGY,
        (),
        tuple(Mapping(name=function.__name__, function=function) for function in REJECTED),
        run,
        scope="invalid registrations",
        code_paths=(__file__,),
    )
    with pytest.raises(CheckFailed) as failure:
        check_pipeline(pipeline, static=False)
    findings = [f for f in failure.value.report["findings"] if f["code"] == "mapping.contract"]
    # Every registration is reported independently, and each names its own problem.
    assert {f["subject"] for f in findings} == {function.__name__ for function in REJECTED}
    for function, message in REJECTED.items():
        reported = [f for f in findings if f["subject"] == function.__name__]
        assert any(message in f["message"] for f in reported), (function.__name__, reported)
        assert all(f["location"]["path"].endswith("test_check_mappings.py") for f in reported)
        assert all(f["location"]["line"] for f in reported)
    assert executed == []
    # Several problems in one signature are collected rather than reported one at a time.
    with pytest.raises(SignatureError) as raised:
        contract(Mapping(name="both", function=not_iterable_and_untyped))
    assert len(raised.value.problems) == 2


def not_iterable_and_untyped(row) -> Value: ...


def test_report_keeps_signature_derived_inputs_outputs_and_concepts():
    pipeline = Pipeline(
        "check:derived",
        TOPOLOGY,
        (),
        (Mapping(name="check:make", function=as_union, requirements=("entity:thing",), evidence=("Why.",)),),
        lambda context: None,
        scope="derived report metadata",
        code_paths=(__file__,),
        requirements={"entity:thing": "check:thing"},
    )
    report = check_pipeline(pipeline, static=False)
    assert report["mappings"]["check:make"] == {
        "inputs": {"row": ["Row"]},
        "outputs": ["Value", "Thing"],
        "concepts": ["check:thing"],
        "requirements": ("entity:thing",),
        "evidence": ("Why.",),
    }
    # An intermediate output needs no topology registration; a graph output does.
    stray: tuple[MappingEntry, ...] = (Mapping(name="check:stray", function=unregistered_output),)
    with pytest.raises(CheckFailed, match="register these graph outputs"):
        check_pipeline(
            replace(pipeline, mappings=stray, requirements={}, deferrals={"entity:thing": "later"}), static=False
        )
